# MCP Server — Phase 1 Design (Read-Only ISO)

## Context

VizzHub exposes operational data across multiple modules (ISO, Tracker, Scorecard, Capacity, Playbook). This design covers Phase 1: a read-only MCP server for the ISO module, enabling Claude to query ISO registries and documents directly.

See `docs/MCP_plan.md` for the full multi-phase plan. This spec covers only the first deliverable.

## Goals

1. Claude can discover and query all ISO registries (schema-driven JSONB data)
2. Claude can read and search ISO documents (policies, procedures)
3. Read-only by design — the MCP server cannot write to the database
4. Works with Claude Code (local) and Claude Desktop (local)
5. Structured for future module additions without refactoring

## Non-Goals (Phase 1)

- Write operations / command queue (Phase 3)
- Other modules: Tracker, Scorecard, Capacity, Playbook (Phase 2)
- Remote HTTP/SSE transport (future)
- OAuth 2.1 authentication (future, when remote transport is added)

## Architecture

### Hybrid approach: B architecture + C write behavior

- **Reads**: Direct DB access via SQLAlchemy with read-only sessions. The MCP server imports backend models and services directly — no duplication.
- **Writes (future)**: Command queue → REST API. The MCP server never writes to the DB, even when write tools are added. All mutations route through the existing VizzHub API with human-in-the-loop approval.

### Why this hybrid

| Concern | Direct DB (reads) | REST API (writes) |
|---|---|---|
| Performance | No HTTP overhead | N/A for reads |
| Safety | `postgresql_readonly` engine | Existing API validation |
| Code reuse | Import models/services directly | No logic duplication |
| Audit trail | N/A for reads | Command queue provides full audit |

### Project structure

```
mcp_server/
├── __main__.py              # python -m mcp_server → stdio
├── server.py                # creates Server, registers tools from each module
├── config.py                # settings (DB URL, user identity)
├── tools/
│   ├── iso.py               # MCP tools for ISO registries + docs
│   ├── tracker.py           # (Phase 2)
│   ├── scorecard.py         # (Phase 2)
│   └── capacity.py          # (Phase 2)
├── data/
│   ├── base.py              # read-only async session factory
│   ├── iso.py               # ISO queries (registries, rows, docs, search)
│   ├── tracker.py           # (Phase 2)
│   ├── scorecard.py         # (Phase 2)
│   └── capacity.py          # (Phase 2)
└── tests/
    ├── conftest.py          # shared fixtures (DB session, seed data)
    ├── test_iso_data.py     # data layer tests (real DB)
    ├── test_iso_tools.py    # tool layer tests (mocked data)
    └── test_integration.py  # end-to-end MCP server tests
```

### Layer responsibilities

| Layer | Does | Does not |
|---|---|---|
| `data/base.py` | Read-only session factory | Commit, write |
| `data/iso.py` | SQLAlchemy queries, returns models | Format for MCP |
| `tools/iso.py` | Registers MCP tools, formats responses | Direct SQL queries |
| `server.py` | Creates server, imports and registers tools | Auto-discovery |

### Backend code reuse

The MCP server imports directly from the backend:

```python
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.services.registry_service import compute_row_fields
```

`PYTHONPATH` includes `backend/` so these imports resolve. No model or service duplication.

## Read-Only Guarantee

The data layer creates a separate SQLAlchemy engine with `postgresql_readonly: True`:

```python
engine = create_async_engine(
    settings.database_url,
    execution_options={"postgresql_readonly": True},
)
```

Even if a bug attempts an INSERT/UPDATE/DELETE, PostgreSQL rejects it at the connection level. The session context manager does not call `commit()` — always implicit rollback.

## MCP Tools (Phase 1)

### `iso_get_registries()`

Returns the catalogue of all registry types with their column schemas.

**Response:**
```json
[
  {
    "slug": "incident-register",
    "name": "Security Incident Register",
    "description": "Log of all information security incidents per ISO 27001 A.16",
    "is_yearly": true,
    "columns": [
      {"key": "incident_number", "label": "Incident Number", "type": "string"},
      {"key": "date", "label": "Date", "type": "date"},
      {"key": "classification", "label": "Classification", "type": "select",
       "options": ["Critical", "High", "Medium", "Low"]}
    ]
  }
]
```

The `description` field uses the semantic, LLM-friendly text already present on every registry type. Columns include type and options so Claude can understand the data structure.

### `iso_get_registry_rows(slug, year?)`

Returns rows for a specific registry, with computed fields injected.

**Parameters:**
- `slug` (string, required): Registry type slug
- `year` (integer, optional): For yearly registries. Defaults to current year if registry is yearly, ignored otherwise.

**Response:**
```json
{
  "registry": "Security Incident Register",
  "slug": "incident-register",
  "year": 2026,
  "total_rows": 3,
  "columns": [...],
  "rows": [
    {
      "id": "uuid...",
      "row_index": 0,
      "data": {
        "incident_number": "INC-2026-001",
        "date": "2026-02-03",
        "classification": "High",
        "risk_score": 8.5,
        "residual_risk": 4.25
      }
    }
  ]
}
```

**Design decisions:**
- Slug as identifier (not UUID) — readable in conversation, stable across environments
- Columns included in response — avoids two-call round-trip for Claude to interpret data
- Computed fields injected via `compute_row_fields()` from backend
- No pagination — ISO registries rarely exceed 100 rows. Add `limit/offset` if needed later
- Attachments excluded — S3 URLs not useful in conversational context

**Slug resolution:** ISO registries live as nodes in the ISO document tree (`iso_doc_nodes`), each linked to a `registry_type` that defines the schema. `data/iso.py` includes a `resolve_registry_node(session, slug)` function that encapsulates this JOIN — given a slug, it returns the registry type and its associated node. Tools never need to know this relationship.

### `iso_get_documents(category?, search?)`

Returns the catalogue of ISO documents with metadata.

**Parameters:**
- `category` (string, optional): Filter by category (policy, procedure, etc.)
- `search` (string, optional): Filter by title (substring match). For full-text content search, use `iso_search_documents` instead.

**Response:**
```json
[
  {
    "slug": "information-security-policy",
    "title": "Information Security Policy",
    "category": "policy",
    "doc_version": "2.1",
    "last_updated": "2026-03-15",
    "summary": "First lines of content..."
  }
]
```

### `iso_get_document(slug)`

Returns full content of a single document.

**Parameters:**
- `slug` (string, required): Document slug

**Response:**
```json
{
  "slug": "information-security-policy",
  "title": "Information Security Policy",
  "category": "policy",
  "doc_version": "2.1",
  "content": "## 1. Purpose\n\nThis policy establishes..."
}
```

### `iso_search_documents(query)`

Full-text search across document content. Returns matching snippets with context.

**Parameters:**
- `query` (string, required): Search terms

**Response:**
```json
[
  {
    "slug": "information-security-policy",
    "title": "Information Security Policy",
    "section": "## 4.3 Encryption",
    "snippet": "...All data in transit must use TLS 1.2+. Remote access requires VPN with AES-256 encryption...",
    "rank": 0.82
  }
]
```

**Implementation:** PostgreSQL native full-text search using `to_tsvector('english', content)` and `ts_headline()` for snippet generation. No extensions required.

`rank` is the PostgreSQL `ts_rank` value, useful only for ordering results. It is not a normalized 0–1 score. Do not interpret it as a percentage of relevance.

The `section` field requires documents to have Markdown headings. `data/iso.py` extracts the nearest preceding heading (`## ...`) from the matched position. If the document has no headings, `section` returns `null`.

## Database Migration

Phase 1 includes an Alembic migration to add a GIN index for full-text search on ISO documents:

- Add a generated `tsvector` column on the document content table
- Create a GIN index on the `tsvector` column
- Follow existing Alembic conventions: raw SQL via `op.execute()`, one statement per call

This is trivial for 30 docs but avoids accumulating tech debt. The index is needed before the search tool can perform well at scale.

## Authentication (Phase 1)

No authentication. The MCP server runs as a local process (stdio transport) on the developer's machine. User identity is declarative via environment variable:

```
MCP_USER_EMAIL=miguel@vizzuality.com
```

Used for logging and future permission checking. Does not authenticate anything.

When HTTP/remote transport is added (future), OAuth 2.1 is implemented as described in `docs/MCP_plan.md`.

## Configuration

### `mcp_server/config.py`

```python
class MCPSettings:
    database_url: str          # PostgreSQL connection string
    mcp_user_email: str        # declarative user identity
```

All settings via environment variables. No config files — the MCP client passes them.

### Claude Code (`.mcp.json`)

```json
{
  "vizzhub": {
    "command": "python",
    "args": ["-m", "mcp_server"],
    "cwd": "/path/to/vizzhub",
    "env": {
      "DATABASE_URL": "postgresql+asyncpg://...",
      "MCP_USER_EMAIL": "miguel@vizzuality.com",
      "PYTHONPATH": "/path/to/vizzhub/backend"
    }
  }
}
```

Added alongside existing MCP servers (shadcn, sonarqube, sentry).

`cwd` is the repo root so that `python -m mcp_server` resolves the package. `PYTHONPATH` includes `backend/` so that imports from `app.modules.*` resolve. Both are needed.

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "vizzhub": {
      "command": "/path/to/vizzhub/backend/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/vizzhub",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://...",
        "MCP_USER_EMAIL": "miguel@vizzuality.com",
        "PYTHONPATH": "/path/to/vizzhub/backend"
      }
    }
  }
}
```

Key difference: Claude Desktop does not inherit the virtualenv, so `command` points to the venv Python directly.

### Credentials

`DATABASE_URL` contains credentials and must not be committed. `.mcp.json` is already in `.gitignore` (or a `.mcp.json.example` with placeholders is committed instead).

### Environment safety

`.mcp.json` is per-developer and not committed. Each developer points `DATABASE_URL` to their local or dev database. Never configure the MCP server to connect to the production database — the read-only session prevents writes but still exposes production data locally, which is unnecessary for development and a risk for ISO 27001 compliance.

## CD / Deployment Impact

### Phase 1 (local): zero impact

The MCP server runs locally, not in production. Considerations for the repo:

- **Dependencies**: `mcp` SDK goes in a separate `requirements-mcp.txt`, not in the main `requirements.txt`. Avoids bloating the production Docker image.
- **Docker build**: `mcp_server/` excluded via `.dockerignore`. Not part of the backend image.
- **CI tests**: MCP tests run in CI alongside backend tests. Same DB setup, same pipeline.

### Future (remote): mount inside FastAPI

When HTTP transport is needed, the MCP server mounts as an endpoint (`/mcp`) inside the existing FastAPI backend. Same container, same deploy, same CD pipeline. Zero new infrastructure.

The code remains a separate directory in the repo (`mcp_server/`) with its own entrypoint for local stdio. A thin FastAPI adapter in the backend delegates to the same server object.

This avoids:
- New Docker container (t3.micro already tight at 2GB)
- New ECR repo
- New CD pipeline configuration

## Testing Strategy

### Data layer tests (`tests/test_iso_data.py`)

Test queries against a real database. Same strategy as backend tests — no DB mocks.

- Verify `get_registry_types` returns types with correct schemas
- Verify `get_registry_rows` filters by year correctly
- Verify `search_documents` returns relevant snippets
- Verify `resolve_registry_node` handles missing slugs

Reuse backend test fixtures (`conftest.py`, async session, test DB).

### Tool layer tests (`tests/test_iso_tools.py`)

Test MCP response formatting. Data layer is mocked — this is a transformation test.

- Verify tool responses have correct structure (slug, name, columns, etc.)
- Verify computed fields are injected into row responses
- Verify error cases (unknown slug, empty results)

### Integration tests (`tests/test_integration.py`)

End-to-end: create MCP server in memory, call tools as Claude would.

- List registries → pick first → get rows → verify data coherence
- Search documents → read matching doc → verify content

Uses MCP Python SDK test utilities (server object directly, no stdio).

### What we don't test

- SQLAlchemy models — already tested in backend
- `compute_row_fields` — already tested in backend
- stdio transport — SDK responsibility
- Claude's interpretation — manual smoke test

### Manual acceptance (Phase 1 complete when)

1. Claude Code: "What ISO registries do we have?" → lists all registry types
2. Claude Code: "How many security incidents in 2026?" → queries incident register, counts
3. Claude Code: "What does our security policy say about remote access?" → searches docs, reads relevant section, answers
4. Claude Desktop: repeat #1 to verify it works there too
5. Claude Code: ask it to "add a new row to the incident register". Verify the MCP server returns a clear message ("Write operations are not available in Phase 1") rather than a PostgreSQL error or stack trace.

## Dependencies

- Python package: `mcp` (official MCP Python SDK) — supports stdio and SSE transports
- No other new dependencies — everything else is already in the backend
