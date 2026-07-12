# MCP Server

VizzHub exposes an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that allows Claude and other MCP clients to query operational data across all modules (ISO, Tracker, Scorecard, Capacity, Playbook, Users, Portfolio) directly from the database. 28 read-only tools + 16 write tools (via command queue) available.

## Architecture

The MCP server supports two transports from the same codebase:

```
Production (HTTPS):

  Claude Code / Desktop
        |
        | HTTPS (Streamable HTTP)
        v
  ALB (hub.vizzuality.com)
        |
        | /mcp*                           → backend:8000
        | /.well-known/oauth-protected-*  → backend:8000
        |
  FastAPI backend
        |
        +-- /mcp/                Streamable HTTP endpoint (single endpoint, POST+GET)
        +-- /mcp/authorize       OAuth → redirects to Google SSO
        +-- /mcp/token           Issues JWT access + refresh tokens
        +-- /mcp/register        Dynamic Client Registration (RFC 7591)
        +-- /mcp/revoke          Token revocation
        +-- /mcp/oauth/callback  Google SSO callback
        +-- /.well-known/oauth-authorization-server/mcp   OAuth metadata (direct)
        +-- /.well-known/oauth-protected-resource/mcp     Resource metadata (direct)


Local development (stdio):

  Claude Code / Desktop
        |
        | stdin/stdout
        v
  python -m mcp_server   (direct DB, no auth)
```

### Key design decisions

- **Two-tier API.** ISO gets a generic schema-driven API (`iso_get_registries`, `iso_get_registry_rows`) because its spreadsheet-like model admits new registries at runtime without MCP changes. Relational modules (Tracker, Scorecard, Capacity, Playbook, Users) get semantic domain-specific tools because their schemas are stable and explicit tool descriptions give the LLM better grounding than a generic row API would.
- **Sub-app, not separate process.** The MCP Starlette app is mounted on the existing FastAPI backend at `/mcp` via `app.mount()`. Same container, same DB pool, same deploy pipeline.
- **Transport-agnostic server.** `create_mcp_server()` factory produces a single `FastMCP` instance with all tools registered once. `__main__.py` uses it over stdio; `main.py` builds `streamable_http_app()` from the same instance and mounts it at `/mcp`. The server object doesn't know which transport is active.
- **Streamable HTTP transport.** The MCP spec deprecated HTTP+SSE (2025-03-26) in favour of **Streamable HTTP**, and as of 2026-06-05 every major client supports it (Claude Code/Desktop, ChatGPT/OpenAI, Gemini, VS Code Copilot, Cursor, Windsurf). VizzHub cut over from SSE to Streamable HTTP on 2026-06-06 (the brief dual-transport phase was collapsed since no clients were connected). Clients connect to the single endpoint at `/mcp/` with `type: "http"`. `streamable_http_path="/"` on the instance makes the endpoint resolve to the mount root (`/mcp/`); the default `/mcp` would double to `/mcp/mcp`. Unlike SSE (each connection spun up its own server), Streamable HTTP needs a `StreamableHTTPSessionManager` whose `run()` task group is driven from FastAPI's `lifespan` — FastAPI does not propagate a mounted sub-app's lifespan.
- **Read-only guarantee.** MCP tool sessions use `postgresql_readonly=True` at the engine level. Even sharing the backend's connection pool, tools cannot write.
- **DNS rebinding protection.** The SDK defaults to `host="127.0.0.1"` which auto-enables DNS rebinding protection with `allowed_hosts=["127.0.0.1:*", "localhost:*"]`. Behind an ALB, the `Host` header is the public domain — pass `TransportSecuritySettings(allowed_hosts=["hub.vizzuality.com"])` to allow it.

## Tools

### `iso_get_registries`

List all ISO registry types with their column schemas.

**Parameters:** None

**Returns:** JSON array of registry types with `slug`, `name`, `description`, `is_yearly`, and `columns` (schema definition).

### `iso_get_registry_rows`

Get all rows from an ISO registry.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slug` | string | yes | Registry type slug (from `iso_get_registries`) |
| `year` | int | no | Year filter for yearly registries. Defaults to current year if the registry uses yearly grouping. |

**Returns:** JSON with registry metadata, column schema, total row count, and all rows with computed fields.

### `iso_get_documents`

List ISO documents (policies, procedures, plans) with metadata and content summary.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `category` | string | no | Filter by category (`policy`, `procedure`, `plan`, `record`, etc.) |
| `search` | string | no | Filter by title substring. For full-text content search, use `iso_search_documents`. |

**Returns:** JSON array of documents with `slug`, `title`, `category`, `doc_version`, `last_updated`, and a 200-character content `summary`.

### `iso_get_document`

Get the full markdown content of a single ISO document.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slug` | string | yes | Document slug (from `iso_get_documents`) |

**Returns:** JSON with `title`, `category`, `doc_version`, and `content` (full markdown).

### `iso_search_documents`

Full-text search across ISO document content using PostgreSQL `tsvector`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | Search terms (e.g. `"encryption remote access"`) |

**Returns:** JSON array of matches with `slug`, `title`, `section` (nearest heading), `snippet` (highlighted excerpt), and `rank`.

### `tracker_get_projects`

List all tracked projects with cost summary. Excludes absence projects.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | no | Filter by project status (`proposal`, `live`, `finished`) |
| `is_billable` | bool | no | Filter by billable flag |

**Returns:** JSON array of projects with `name`, `code`, `budget`, `staff_cost`, `non_staff_cost`, `total_cost`, `burn_percentage`, `income`, and `project_manager`.

### `tracker_get_project_detail`

Full project detail: budget lines, cost summary with per-period breakdown.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |

**Returns:** JSON with project info, `budget_lines` (days/percentage per FA), and `cost_summary` with per-period breakdown.

### `tracker_get_project_time`

Time allocation for a project grouped by user or functional area.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |
| `group_by` | string | no | `"user"` (default) or `"functional_area"` |

**Returns:** JSON array of groups with `total_days`, `total_cost`, and per-period breakdown.

### `tracker_get_project_invoices`

Invoices for a project with effective status (accounts for postponements).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |

**Returns:** JSON array of invoices with `amount`, `milestone`, `due_date`, `status` (effective), `postpone_count`.

### `tracker_get_project_progress`

Progress history for a project: % completed per period with delta.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |

**Returns:** JSON array of progress reports with `percentage` (0-1) and `delta` (change from prior period).

### `tracker_get_periods`

Reporting periods with report counts.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | no | Filter by period status (`unstarted`, `active`, `finished`) |

**Returns:** JSON array of periods with `date`, `status`, `base_rate`, `report_count`, `confirmed_count`.

### `scorecard_get_project_scores`

All scored projects with their latest overall score and dimension breakdown.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | no | Filter by project status |

**Returns:** JSON array of projects with `score` (0-100), 8 `dimensions` (time, cost, quality, value, satisfaction, flow, engineering, risk), and `dora` classification.

### `scorecard_get_project_scorecard`

Full scorecard for a single project: indicators, dimensions, DORA, EVM, milestones.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |
| `year` | int | no | Period year (requires `month`) |
| `month` | int | no | Period month 1-12 (requires `year`) |

**Returns:** JSON with `score`, `dimensions`, `indicators` (normalized 0-1), `dora` metrics, `evm` data, and `milestones`.

### `scorecard_get_project_history`

Score trend for a project over recent periods.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | yes | Project UUID |
| `limit` | int | no | Max periods (default 12, max 48) |

**Returns:** JSON array of periods with `score`, `dimensions`, `key_indicators` (SPI, CPI, lead time, etc.).

### `scorecard_get_global_metrics`

Organization-wide averaged scores and indicators by month.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | int | no | Max months (default 12, max 48) |

**Returns:** JSON array of monthly records with averaged `scores` and `indicators` across all projects, plus `project_count`.

### `capacity_get_insights`

Billable allocation overview by functional area and period.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_month` | string | no | YYYY-MM format. Defaults to 6 months ago. |
| `end_month` | string | no | YYYY-MM format. Defaults to current month. |

**Returns:** JSON array of periods with per-FA `billable_pct`, `absence_pct`, and `user_count`.

### `capacity_get_fa_detail`

Per-user breakdown for a functional area.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `fa` | string | yes | FA short code: `FE`, `BE`, `Design`, `PM`, `Sci`, `Coms` |
| `start_month` | string | no | YYYY-MM format |
| `end_month` | string | no | YYYY-MM format |

**Returns:** JSON array of periods with per-user `billable_pct`, `absence_pct`, `billable_project_count`.

### `capacity_get_user_detail`

Per-project breakdown for a specific user.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user_id` | string | yes | User UUID |
| `start_month` | string | no | YYYY-MM format |
| `end_month` | string | no | YYYY-MM format |

**Returns:** JSON array of periods with per-project `percentage` and `absence_pct`.

### `capacity_get_allocation`

Averaged allocation across finished periods.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `view` | string | no | `"users"` (default) or `"projects"` |
| `start_month` | string | no | YYYY-MM format |
| `end_month` | string | no | YYYY-MM format |

**Returns:** JSON with `periods_used` and allocation segments (by user or by project).

### `playbook_get_tree`

Hierarchical navigation tree of the playbook.

**Parameters:** None

**Returns:** JSON tree with `title`, `slug`, `type` (page/group), `is_public`, and `children`.

### `playbook_get_article`

Full markdown content of a playbook article.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slug` | string | yes | Article slug (from `playbook_get_tree`) |

**Returns:** JSON with `title`, `content` (markdown), `version`, `is_public`.

### `playbook_search_articles`

Search playbook articles by title and content.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | Search terms |

**Returns:** JSON array of matching articles with `title`, `slug`, `summary`.

### `users_get_team`

Get the team directory — list of users with their role and area.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `active_only` | boolean | no | Only active users (default: true) |
| `functional_area` | string | no | Filter by FA name (e.g. "Frontend Developer") |

**Returns:** JSON array of users with `id`, `name`, `email`, `functional_area`, `rate_code`, `dedication`, `roles`, `slack_display_name`, `requires_project_reporting`.

### `users_get_detail`

Get full profile for a specific user.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user_id` | string | yes | User UUID |

**Returns:** JSON object with full profile: `name`, `first_name`, `last_name`, `email`, `functional_area`, `rate_code`, `rate_value`, `dedication`, `roles`, `slack_display_name`, `last_login_at`, `requires_project_reporting`.

### `users_get_functional_areas`

List all functional areas (team skill categories).

**Parameters:** None

**Returns:** JSON array of functional areas with `id` and `name`.

### `users_get_rates`

List all billing rate bands.

**Parameters:** None

**Returns:** JSON array of rate bands with `id`, `code` (A-D), and `value`.

### `portfolio_search_programs`

Full-text search over the program catalogue — name and profile narrative (objective, short description, impact story, web copy, main partner). Gated `portfolio:view`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | Free-text query (min 2 chars; websearch syntax supported, e.g. quoted phrases) |
| `limit` | int | no | Max results (default 10, clamped to 50) |

**Returns:** JSON array ordered by relevance (name matches first) with `program_id`, `name`, `stage`, `snippet` (highlighted fragment with `<b>` tags), and `url`.

## Authentication

### Overview

The MCP server uses OAuth 2.1 with PKCE, delegating user authentication to VizzHub's existing Google SSO. Every MCP call carries a JWT tied to a real VizzHub user, providing a complete audit trail (who, when, which tool) for ISO 27001 compliance.

```
Claude Code                       VizzHub Backend
    |                                    |
    |-- POST /mcp/ ------------------>   |
    |<-- 401 + WWW-Authenticate ------   |  (no token)
    |                                    |
    |-- GET /.well-known/oauth-...  ->   |  (discover OAuth)
    |                                    |
    |-- GET /mcp/authorize ---------->   |
    |<-- 302 Google OAuth consent ----   |  (redirect to Google)
    |                                    |
    |     [User authenticates]           |
    |                                    |
    |<-- 302 /mcp/oauth/callback ----   |  (Google redirects back)
    |                                    |  (creates auth code + user info)
    |<-- 302 redirect_uri?code=... --   |  (redirects to Claude)
    |                                    |
    |-- POST /mcp/token ------------->   |  (exchange code for JWT)
    |<-- { access_token, refresh } ---   |
    |                                    |
    |-- POST /mcp/ + Bearer JWT ----->   |  (tool calls work)
```

### Components

**`VizzHubTokenVerifier`** (`mcp_server/auth/token_verifier.py`)

Implements the MCP SDK `TokenVerifier` protocol. Validates JWTs using `jose.jwt.decode()` with:
- Shared secret: same `JWT_SECRET_KEY` as the backend
- Audience: `vizzhub-mcp` (prevents UI session tokens from being accepted)
- Issuer: `vizzhub`

Returns an `AccessToken` with `client_id` (user UUID), `scopes`, and `expires_at`.

**`VizzHubOAuthProvider`** (`mcp_server/auth/provider.py`)

Implements the MCP SDK `OAuthAuthorizationServerProvider` protocol. Adapts the existing Google SSO flow to the OAuth 2.1 protocol that MCP clients expect.

Key methods:
| Method | Behavior |
|--------|----------|
| `authorize` | Stores MCP params in DB (5-min TTL), returns Google OAuth URL |
| `exchange_authorization_code` | Verifies PKCE (via SDK), issues JWT + refresh token |
| `exchange_refresh_token` | Rotates tokens (delete old, create new) |
| `load_access_token` | Delegates to `VizzHubTokenVerifier` |
| `revoke_token` | Deletes refresh token from DB |

**`google_oauth_callback`** (`mcp_server/auth/callback.py`)

Starlette endpoint at `/mcp/oauth/callback`. Handles the Google redirect:
1. Loads the MCP state row from DB
2. Exchanges Google auth code for ID token
3. Verifies domain (`@vizzuality.com`)
4. Looks up user, resolves permissions
5. Creates a new auth code with user info (60s TTL)
6. Redirects to MCP client with the new code

### JWT claims

Access tokens are HS256 JWTs with:

```json
{
  "sub": "user-uuid",
  "email": "user@vizzuality.com",
  "client_id": "oauth-client-id",
  "roles": ["user", "admin"],
  "permissions": ["*"],
  "scopes": ["read"],
  "iss": "vizzhub",
  "aud": "vizzhub-mcp",
  "iat": 1744300000,
  "exp": 1744307200
}
```

Access tokens expire in 2 hours. Refresh tokens expire in 30 days and are rotated on use.

### OAuth state storage

OAuth state (codes, refresh tokens, client registrations) is stored in PostgreSQL:
- `mcp_oauth_clients` — OAuth clients (pre-registered + dynamically registered)
- `mcp_oauth_codes` — authorization codes (60s TTL after callback, 5min TTL during Google flow)
- `mcp_oauth_refresh_tokens` — refresh tokens (30-day TTL)

An ARQ cron job runs daily at 3 AM UTC to purge expired rows.

### Client registration

Dynamic Client Registration (RFC 7591) is enabled. Claude Code registers itself as an OAuth client on first connection — the SDK generates `client_id` and `client_secret`, which the provider stores in `mcp_oauth_clients`.

A pre-registered fallback client also exists: credentials are generated by OpenTofu, stored in Secrets Manager, and auto-seeded into the DB on backend startup.

**Implementation note:** The SDK's `RegistrationHandler` ignores the return value of `register_client()` — it returns its own `client_info` object. The provider must store the SDK-generated IDs, not create new ones.

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ENABLED` | `false` | Enable the HTTP MCP sub-app |
| `MCP_BASE_URL` | `""` | Public URL (e.g. `https://hub.vizzuality.com/mcp`) |
| `MCP_OAUTH_CLIENT_ID` | `""` | Pre-registered OAuth client ID (from Secrets Manager) |
| `MCP_OAUTH_CLIENT_SECRET` | `""` | Pre-registered OAuth client secret (from Secrets Manager) |

These are set automatically in production by the deploy pipeline reading from Secrets Manager.

### Local setup (stdio)

For local development, the MCP server runs via stdio with no auth:

**Claude Code** — use the wrapper script:
```json
// .mcp.json
{
  "mcpServers": {
    "vizzhub-local": {
      "command": "bash",
      "args": ["./scripts/run-mcp-server.sh"]
    }
  }
}
```

The script sets `PYTHONPATH=backend` and loads `DATABASE_URL` from `backend/.env`.

**Claude Desktop** — use the direct Python path (macOS blocks bash scripts):
```json
// claude_desktop_config.json
{
  "mcpServers": {
    "vizzhub": {
      "command": "/path/to/python",
      "args": ["-m", "mcp_server"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/dbname",
        "PYTHONPATH": "/path/to/vizzhub/backend:/path/to/vizzhub"
      }
    }
  }
}
```

### Remote setup (HTTP)

For production access, clients connect over **Streamable HTTP** with OAuth authentication. The endpoint is the single URL `https://hub.vizzuality.com/mcp`. Both `/mcp` and `/mcp/` work — some clients (e.g. the Claude Desktop connector UI) strip the trailing slash, so the backend serves the transport at the bare path too (see `_McpBarePathApp` in `main.py`).

**Claude Code** — `.mcp.json` in the repo root:
```json
{
  "mcpServers": {
    "vizzhub-remote": {
      "type": "http",
      "url": "https://hub.vizzuality.com/mcp/"
    }
  }
}
```

Or via CLI: `claude mcp add --transport http vizzhub-remote https://hub.vizzuality.com/mcp/`

**Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "vizzhub": {
      "url": "https://hub.vizzuality.com/mcp/"
    }
  }
}
```

On Windows the config file is at `%APPDATA%\Claude\claude_desktop_config.json`.

> **Migrating from the old SSE config?** The deprecated SSE transport (`type: "sse"`, url `…/mcp/sse`) was removed on 2026-06-06. Replace it with the `type: "http"` config above pointing at `…/mcp/`.

On first connection, the client discovers OAuth endpoints via `/.well-known/oauth-authorization-server` and opens a browser for Google SSO authentication. After login, the token is cached and reused until it expires.

## Infrastructure

### ALB routing

The ALB routes `/mcp*` to the backend target group at priority 50:

| Priority | Pattern | Target |
|----------|---------|--------|
| 1-4 | Scanner blocks | Fixed 403 |
| 50 | `/mcp*`, `/.well-known/oauth-protected-resource*`, `/.well-known/oauth-authorization-server*` | backend:8000 |
| 99 | `/health` | backend:8000 |
| 100 | `/api/*` | backend:8000 |
| default | `/*` | frontend:5173 |

**Note:** Both `/.well-known/oauth-*` patterns are required because the MCP SDK expects OAuth metadata at the domain root (per RFC 9728 and RFC 8414), not under the `/mcp` mount. FastAPI serves the metadata JSON directly at these paths (not via redirect — the MCP SDK client doesn't follow 307 redirects).

### Secrets Manager

The MCP OAuth client credentials are stored in `/${project}/${env}/mcp-oauth`:
```json
{
  "client_id": "auto-generated-by-tofu",
  "client_secret": "auto-generated-by-tofu"
}
```

Generated by OpenTofu (`random_password`), read by the deploy pipeline into the backend `.env`.

### Database tables

Three tables created by migrations 049-050:

| Table | Purpose | TTL |
|-------|---------|-----|
| `mcp_oauth_clients` | Pre-registered OAuth clients | None |
| `mcp_oauth_codes` | Authorization codes | 60s (post-callback) |
| `mcp_oauth_refresh_tokens` | Refresh tokens | 30 days |

## Testing

```bash
# Run all MCP tests (72 tests)
PYTHONPATH=backend:. pytest mcp_server/tests/ -v

# Run specific test suites
PYTHONPATH=backend:. pytest mcp_server/tests/test_token_verifier.py -v
PYTHONPATH=backend:. pytest mcp_server/tests/test_oauth_provider.py -v
PYTHONPATH=backend:. pytest mcp_server/tests/test_oauth_callback.py -v
PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v
PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v
PYTHONPATH=backend:. pytest mcp_server/tests/test_integration.py -v

# Run cleanup job tests
cd backend && pytest tests/worker/test_cleanup_mcp_oauth.py -v
```

## Data model guide (instructions)

The MCP server delivers context to clients in two layers:

**1. Instructions (~1.5KB, always in context)**

A short text in `server.py` (`_INSTRUCTIONS`) that is injected into the client's context at connection time via the MCP `InitializeResult`. Contains: module overview table, key joins, FA mapping, app URL patterns, and core conventions. This is what Claude sees immediately without any tool calls.

**2. Resource `vizzhub://data-model` (16KB, on demand)**

The full data model guide loaded from [`docs/mcp/vizzhub-skill.md`](mcp/vizzhub-skill.md). Contains detailed tool reference tables, cross-module query patterns, registry lists (yearly vs non-yearly), and expanded conventions. Claude Code can read this via `ReadMcpResourceTool`; Claude Desktop lists it but cannot read it (client limitation).

The same file is also installed as a Claude Code skill (`vizzhub-data-model`), so Claude Code gets the full guide via skill invocation as well.

**To update:** Edit `_INSTRUCTIONS` in `server.py` for short context, or `docs/mcp/vizzhub-skill.md` for the full guide. Both are read once at module import time — changes require a deploy/restart.

**Why this split?** The full 16KB guide exceeded client context limits when sent as instructions. Short instructions always arrive; the full guide is available on demand for complex query planning. The Dockerfile must COPY `docs/mcp/vizzhub-skill.md` into the image (`--chmod=555` to allow directory traversal).

## Project structure

```
mcp_server/
├── __init__.py
├── __main__.py              # Stdio entrypoint: mcp.run(transport="stdio")
├── config.py                # Settings for stdio mode (DATABASE_URL)
├── server.py                # create_mcp_server() factory — instructions + data-model resource
├── auth/
│   ├── token_verifier.py    # VizzHubTokenVerifier (JWT validation)
│   ├── provider.py          # VizzHubOAuthProvider (OAuth adapter)
│   └── callback.py          # Google SSO callback endpoint
├── data/
│   ├── base.py              # Read-only session management
│   └── iso.py               # ISO data queries (registries, documents, search)
├── tools/
│   └── iso.py               # 5 MCP tool definitions + register_iso_tools()
└── tests/
    ├── conftest.py           # Shared fixtures (test DB, session override)
    ├── test_token_verifier.py
    ├── test_oauth_provider.py
    ├── test_oauth_callback.py
    ├── test_iso_data.py
    ├── test_iso_tools.py
    └── test_integration.py
```

## Troubleshooting

### `/mcp/` returns 404 "Not Found"

The MCP sub-app didn't mount. Check container logs:
```bash
docker logs hub-backend 2>&1 | grep mcp
```

Common causes:
- `MCP_ENABLED` not set to `true` in `.env`
- `mcp_server/` not included in the Docker image (check Dockerfile build context is repo root, not `./backend`)
- `mcp` package missing from `backend/uv.lock` (it's a runtime dep in `pyproject.toml` — sync with `cd backend && uv sync`)
- Mount failed with exception (look for `mcp_server_mount_failed` in logs)

### `/mcp` returns 404 without trailing slash

By default the Streamable HTTP endpoint resolves to `/mcp/` (the sub-app is mounted at `/mcp` with `streamable_http_path="/"`, and `redirect_slashes` is off). Some clients — notably the Claude Desktop connector UI — strip the trailing slash and POST to bare `/mcp`, which Starlette's `Mount` won't forward. `_McpBarePathApp` (`main.py`) fixes this: it registers a top-level route for the bare `/mcp` that rewrites the path to `/` and feeds the request through the same sub-app, so both `/mcp` and `/mcp/` work. If bare `/mcp` 404s in a deploy, check that route is registered before the `app.mount("/mcp", …)` call.

### "SDK auth failed: Failed to parse JSON"

Two possible causes:

1. **ALB not routing `.well-known` to backend.** The `WWW-Authenticate` header points to `/.well-known/oauth-protected-resource/mcp` at the domain root. If the ALB doesn't route it to the backend, the frontend serves HTML instead of JSON. Fix: ensure the ALB rule includes `/.well-known/oauth-protected-resource*` → backend.

2. **Redirect instead of direct response.** The MCP SDK client does NOT follow HTTP 307 redirects. If the `/.well-known/oauth-protected-resource/{path}` endpoint uses `RedirectResponse` to proxy to `/mcp/.well-known/...`, the SDK receives an empty 307 body and fails to parse it as JSON. Fix: serve the resource metadata JSON directly from the FastAPI endpoint, not via redirect.

### "Cannot specify both auth_server_provider and token_verifier"

`FastMCP` forbids passing both. When using `auth_server_provider`, the SDK creates its own verifier via the provider's `load_access_token` method. Remove `token_verifier` from `create_mcp_server()`.

### `.mcp.json` schema validation error

Use `type: "http"` for the Streamable HTTP endpoint (`/mcp/`). Note: the value is `"http"`, not `"streamable-http"`. (The legacy `type: "sse"` endpoint was removed on 2026-06-06.)

### "Incompatible auth server: does not support dynamic client registration"

The MCP SDK requires a `registration_endpoint` in the OAuth authorization server metadata. Two things needed:

1. Enable `ClientRegistrationOptions(enabled=True)` in `AuthSettings` — without this, the SDK won't create the `/register` route.
2. Include `registration_endpoint` in the `/.well-known/oauth-authorization-server/{path}` response served by FastAPI.

### "Client ID not found" after successful registration

The SDK's `RegistrationHandler` generates `client_id` and `client_secret`, passes them to `register_client()`, then returns **its own copy** (ignoring the return value). If `register_client()` generates different IDs and stores those, the client will use the SDK's IDs which don't exist in the DB.

Fix: `register_client()` must store `client_info.client_id` and `client_info.client_secret` as-is, not generate new ones.

### OAuth flow doesn't start

1. Check `/.well-known/oauth-authorization-server/mcp` returns JSON (not HTML): `curl https://hub.vizzuality.com/.well-known/oauth-authorization-server/mcp`
2. Check the Google Cloud Console has `https://hub.vizzuality.com/mcp/oauth/callback` as authorized redirect URI
3. Check the OAuth client is seeded: look for `mcp_oauth_client_seeded` in container logs

### Deploy order

When changing MCP infrastructure:
1. `tofu apply` first (creates secrets in Secrets Manager)
2. Push to main (deploy reads secrets into `.env`)

If reversed, the deploy will fail to read the MCP OAuth secret.

### "Task group is not initialized" RuntimeError

The `StreamableHTTPSessionManager` requires its `run()` context manager to initialize an `anyio` task group. When mounting the MCP Starlette sub-app via `app.mount()`, FastAPI does **not** propagate the sub-app's lifespan — so `run()` never gets called.

Fix: store `mcp_server.session_manager` on `app.state` during setup, then run it explicitly in FastAPI's lifespan:

```python
mcp_mgr = getattr(app.state, "mcp_session_manager", None)
if mcp_mgr:
    async with mcp_mgr.run():
        yield
else:
    yield
```

### "Invalid Host header" / 421 status after auth

The SDK defaults to `host="127.0.0.1"` which auto-enables DNS rebinding protection with `allowed_hosts=["127.0.0.1:*", "localhost:*"]`. Behind an ALB, the `Host` header is the public domain (e.g. `hub.vizzuality.com`), which isn't in the allowlist.

Fix: pass `TransportSecuritySettings` with the public hostname when creating the MCP server:

```python
from mcp.server.transport_security import TransportSecuritySettings

TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["hub.vizzuality.com"],
)
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | Done | Read-only ISO tools (stdio) |
| 1.5 | Done | HTTP transport + OAuth + deployment |
| 2 | Done | Read-only relational modules (Tracker, Scorecard, Capacity, Playbook, Users) |
| 3A | Done | Permission layer (McpUserContext, @mcp_requires, ISO doc visibility) |
| 3B | Done | Command queue — write operations for ISO docs, registries, Playbook |
| 4 | Planned | Transactions (Saga pattern with cross-command references) |
| 5 | Planned | Policy engine (risk-based routing, role-based approval) |

Phase 4 adds cross-command references via a saga pattern: commands in the same transaction can reference the result of earlier commands (e.g. a corrective action that references a nonconformity created in the same transaction) using a `$ref` syntax resolved at execution time. If any command fails, the transaction rolls back.

## Write Operations (Command Queue)

All write operations go through a human-in-the-loop command queue. Tools enqueue commands that require explicit approval before execution.

### ISO Docs Write Tools (9)

| Tool | Permission | Description |
|---|---|---|
| `iso_create_page` | `iso_docs:edit` | Create a new page under a group |
| `iso_update_page_content` | `iso_docs:edit` | Update page markdown content (versioned) |
| `iso_patch_page_content` | `iso_docs:edit` | Apply search-replace patches to page content (versioned) |
| `iso_update_page_metadata` | `iso_docs:edit` | Update metadata fields (partial update) |
| `iso_update_node` | `iso_docs:edit` | Rename or move a node |
| `iso_delete_node` | `iso_docs:edit` | Delete a leaf node (no children) |
| `iso_create_registry_row` | `iso_docs:edit` | Add a row to a registry |
| `iso_update_registry_row` | `iso_docs:edit` | Update fields in a registry row |
| `iso_delete_registry_row` | `iso_docs:edit` | Delete a registry row |

### Playbook Write Tools (4)

| Tool | Permission | Description |
|---|---|---|
| `playbook_create_article` | `playbook:edit` | Create a new article under a group |
| `playbook_update_article_content` | `playbook:edit` | Update article markdown content (versioned) |
| `playbook_update_node` | `playbook:edit` | Rename or move a node |
| `playbook_delete_node` | `playbook:edit` | Delete a leaf node (no children) |

### Queue Management Tools (4)

| Tool | Description |
|---|---|
| `get_pending_commands` | List your pending commands (optional module filter) |
| `approve_command` | Approve and execute a command (requires module permission) |
| `approve_all` | Approve and execute every pending command in one call (optional module filter) |
| `reject_command` | Reject a command (requires module permission) |

### Command Flow

1. Claude calls a write tool → command is enqueued with `status: queued`
2. Claude presents the human-readable summary to the user for review
3. User confirms → Claude calls `approve_command` → command executes
4. User declines → Claude calls `reject_command` → command is discarded

### REST API

Commands are also accessible via REST for future UI integration:

```
GET  /api/commands?status=pending&module=iso_docs
POST /api/commands/{id}/approve
POST /api/commands/{id}/reject
```

### Safety

- Delete node operations only work on leaf nodes (no children). Cascading deletes are blocked.
- All write operations require the same permission as the corresponding UI action.
- Failed executions are recorded with error details for audit.
- User attribution: all changes are attributed to the authenticated user, not "system".

### Audit trail

Every row in `command_transactions` + `command_queue` answers *what* was proposed (action, target, payload), *why* (context, linked process), *who* requested it (session), *when* it was proposed and executed, *who* approved it, and *what happened* (result or error). This is the audit evidence used to demonstrate AI change control for ISO 27001 / ISO 9001 audits.

## Direct-Write Exception: Telemetry

The "all writes go through the command queue" rule has one deliberate exception: **internal telemetry**. Today this is used only by `track_install` (bumps `install_count` + `last_installed_at` after a successful `devstack_get_installable`).

### Why it's allowed

Command queue exists to protect against two failure modes:
1. **Malicious writes** — prompt injection, compromised sessions. Rare but high-impact.
2. **Hallucinated writes** — the LLM calls a tool because it *thinks* it should, not because the user asked. Common and low-impact individually, but eroding.

Telemetry sidesteps both concerns when it meets all of these criteria:
- **No user-visible state change.** The effect is invisible to the human operating the app; at worst it skews admin-facing analytics.
- **No value from the caller.** The UPDATE is a fixed column expression (e.g. `install_count + 1`). The LLM cannot inject a value that gets written.
- **Failure-swallowing.** A DB error in the telemetry path logs and returns — it cannot cascade into the user-facing response.
- **Scoped permission.** The calling tool is already permission-gated; the side effect cannot exceed the read surface of the tool that triggered it.

If any of those is missing, the write goes through the command queue instead.

### What to do when adding a new direct write

1. Write down which of the four criteria above apply in the PR description. If any is unclear, default to the command queue.
2. Use `get_write_session()` from `mcp_server/data/base.py` inside a try/except that logs with a `{entity}_tracker_failed` event name.
3. Fix the UPDATE shape — never interpolate caller-supplied values into `.values(...)`.
4. Add a test that verifies the counter is NOT bumped on failure paths (e.g. `InstallableError`, inactive entry).
5. After the 3rd direct-write use case, extract a shared `fire_and_log_write` helper instead of duplicating the try/except.

### What direct writes never do

- Modify user-visible content (pages, articles, registry rows, projects, users)
- Change permissions or access control
- Expose data outside the caller's read scope
- Retry on failure (one attempt, log, move on)

If you find yourself reaching for one of those, the answer is the command queue, not a new direct-write exception.
