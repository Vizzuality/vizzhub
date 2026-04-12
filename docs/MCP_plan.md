# VizzHub MCP Architecture Plan

## Context

VizzHub is Vizzuality's internal hub application aggregating multiple operational modules:

| Module        | Purpose                                                                                                                                    | Data Model                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| **ISO**       | ISO 9001 + ISO 27001 documentation and records (incidents, nonconformities, risk treatment plans, audit results, corrective actions, etc.) | Generic spreadsheet-like schema: documents → rows → cells. Flexible, schema-per-document. |
| **Tracker**   | Project budget tracking and time reporting                                                                                                 | Relational: projects, allocations, time entries, budget lines                             |
| **Scorecard** | Project and organizational performance metrics                                                                                             | Relational: scorecards, dimensions, indicators, scores                                    |
| **Capacity**  | Team capacity planning and resource allocation                                                                                             | Relational: team members, availability, assignments, periods                              |
| **Playbook**  | Internal knowledge base and process documentation (markdown content published to S3/CloudFront)                                            | Relational: articles, categories, versions                                                |

The ISO module uses a generic spreadsheet-like schema where records are stored as documents with flexible rows and columns. All other modules use conventional relational models with domain-specific tables and relationships.

This plan describes the architecture for exposing all VizzHub modules via an MCP (Model Context Protocol) server, enabling Claude to read operational data across the platform, generate documents (e.g., Management Review Reports, capacity reports, budget summaries), and propose write operations through a human-approved command queue.

## Goals

1. Enable Claude to read data from all VizzHub modules via MCP
2. Enable Claude to propose write operations (new records, updates) without direct execution
3. Ensure every write operation requires explicit human approval before execution
4. Maintain full auditability of all proposed and executed actions (critical for ISO compliance, valuable across all modules)
5. Keep the existing VizzHub API unchanged — the command queue is a new layer, not a rewrite
6. Support both generic (ISO) and relational (Tracker, Scorecard, Capacity, Playbook) data models through a unified MCP interface

## Design Patterns Used

| Pattern               | Purpose                                                                                                                    | Reference                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| **Command Pattern**   | Encapsulate write operations as serializable objects with all parameters, enabling storage, review, and deferred execution | GoF Design Patterns                       |
| **Outbox Pattern**    | Write operations are persisted to a queue table before execution, decoupling intent from side effects                      | Microservices / Event-Driven Architecture |
| **Saga Pattern**      | Group multiple dependent commands into a transaction with ordered execution and rollback on failure                        | Distributed Systems (Chris Richardson)    |
| **Human-in-the-Loop** | Require explicit human approval before any queued command is executed                                                      | BPM / Workflow Engines                    |

Analogies: the flow is similar to **database migrations** (review then apply), **Terraform plan → apply** (preview changes before execution), or **pull requests** (propose, review, merge).

## MCP API Surface

The MCP server exposes tools organized in two tiers: a generic layer for the ISO module (spreadsheet-like schema) and domain-specific endpoints for relational modules.

### Tier 1: Generic API (ISO Module)

These endpoints work with the ISO module's flexible document/row schema.

#### `iso.get_records()`

Returns the catalogue of all available ISO documents/registers with metadata.

```json
// Response
[
  {
    "id": "incident-register",
    "name": "Security Incident Register",
    "description": "Log of all information security incidents per ISO 27001 A.16",
    "columns": ["Incident Number", "Date", "Classification", "Reason", "Description", "Affected Clients/Suppliers", "Cause", "Detected By", "Immediate Actions"]
  },
  {
    "id": "nonconformities",
    "name": "Nonconformity Register",
    "description": "...",
    "columns": [...]
  }
]
```

Purpose: allows Claude to discover what records exist and understand their structure before querying. Makes the system self-describing — new registers added to VizzHub are automatically discoverable without updating the MCP or any skill.

#### `iso.get_document_rows(document_id, period?)`

Returns the rows for a specific document, optionally filtered by period.

```json
// Request
{ "document_id": "incident-register", "period": "2026-Q1" }

// Response
{
  "document_id": "incident-register",
  "columns": ["Incident Number", "Date", "Classification", ...],
  "rows": [
    { "Incident Number": "INC-2026-001", "Date": "2026-02-03", "Classification": "High", ... },
    { "Incident Number": "INC-2026-002", "Date": "2026-03-15", "Classification": "Low", ... }
  ]
}
```

### Tier 2: Domain-Specific API (Relational Modules)

These endpoints expose the relational modules with semantically meaningful operations that match their data models.

#### Tracker

```
tracker.get_projects(status?, period?)          → List projects with budget summary
tracker.get_project_detail(project_id)          → Full project: budget lines, allocations, actuals
tracker.get_time_entries(project_id?, user?, period?) → Time entries with filters
tracker.get_budget_summary(project_id, period?) → Budget vs. actuals breakdown
```

#### Scorecard

```
scorecard.get_scorecards(period?)               → List scorecards with overall scores
scorecard.get_scorecard_detail(scorecard_id)    → Full scorecard: dimensions, indicators, scores
scorecard.get_indicator_history(indicator_id)    → Historical values for trend analysis
```

#### Capacity

```
capacity.get_team_availability(period)          → Team members with available/allocated hours
capacity.get_project_allocations(project_id?)   → Who is allocated where and for how much
capacity.get_utilization(period, team?)          → Utilization rates by team or individual
```

#### Playbook

```
playbook.get_articles(category?)                → List articles with metadata
playbook.get_article(article_id)                → Full article content (markdown)
playbook.search_articles(query)                 → Full-text search across playbook
```

### Tier 2 Design Rationale

The relational modules get semantic endpoints rather than generic row access because:

- Their data models have explicit relationships (project → budget lines → time entries) that a generic row API would flatten and lose
- Queries are naturally domain-specific ("show me budget vs. actuals for project X" rather than "get rows from table Y")
- The relational schema is stable and known ahead of time, unlike the ISO module where new registers can be created at any time
- Semantic endpoints produce better MCP tool descriptions, which directly improve Claude's ability to select the right tool and interpret results

### Write Operations (queued, require approval — all modules)

All write operations across all modules are routed through the command queue. The action field in the command identifies the target operation.

#### Generic writes (ISO module)

#### `iso.create_row(document_id, data)`

Proposes the creation of a new row in a document. Does **not** execute immediately — creates a pending command in the queue.

```json
// Request
{ "document_id": "nonconformities", "data": { "Description": "...", "Severity": "Major", ... } }

// Response
{
  "status": "queued",
  "command_id": "cmd-001",
  "transaction_id": "txn-001",
  "message": "Action queued for approval. Will create row in 'nonconformities' once approved."
}
```

The MCP tool description must explicitly state: _"This operation does not execute immediately. It creates a pending command that requires human approval in VizzHub before execution."_ This ensures Claude communicates the queued status to the user correctly.

#### Domain-specific writes (relational modules)

Write operations for relational modules use semantic actions that map to their domain:

```
tracker.log_time(project_id, user, hours, date, description)    → Queue time entry
tracker.update_budget_line(line_id, data)                        → Queue budget update
capacity.update_allocation(user, project_id, hours, period)      → Queue allocation change
playbook.create_article(title, category, content)                → Queue new article
playbook.update_article(article_id, content)                     → Queue article edit
```

All follow the same pattern: the MCP call does not execute directly but creates a pending command in the queue. The response always includes `status: "queued"` and a `command_id`.

### Queue Management Operations

#### `get_pending_commands(transaction_id?)`

Returns pending commands, optionally filtered by transaction.

```json
// Response
[
  {
    "command_id": "cmd-001",
    "transaction_id": "txn-001",
    "action": "create_row",
    "target_document": "nonconformities",
    "payload": { "Description": "...", "Severity": "Major" },
    "context": "Management Review Report Q1 2026 generation",
    "requested_by": "claude_session_xyz",
    "requested_at": "2026-04-03T10:30:00Z",
    "status": "pending"
  }
]
```

#### `approve_command(command_id)` / `reject_command(command_id)`

Changes a pending command's status. On approval, the command is executed against the real VizzHub API.

```json
// Response (approve)
{
  "command_id": "cmd-001",
  "status": "approved",
  "result": { "id": 42, "status": "created" },
  "executed_at": "2026-04-03T10:35:00Z"
}
```

The MCP tool description for `approve_command` must state: _"This action requires explicit user confirmation before calling. Never call without the user's direct approval."_

## Authentication & Authorization

### Overview

VizzHub uses Google OAuth SSO for authentication. The MCP server inherits the same identity and permission model, ensuring that a user accessing VizzHub through Claude has exactly the same access as through the VizzHub UI.

The MCP server acts as an **OAuth 2.1 Resource Server** (per MCP spec). VizzHub acts as the **Authorization Server**, delegating user authentication to Google OAuth (existing SSO) and issuing its own MCP access tokens with embedded permissions.

### Authentication Flow

```
Claude ──► MCP Server ──► 401 Unauthorized (no token)
                          ↓
Claude ──► VizzHub Auth Endpoint ──► Google OAuth SSO ──► User authenticates
                          ↓
VizzHub identifies user, loads internal permissions (role, modules, projects)
                          ↓
VizzHub issues JWT access token (2h TTL) + refresh token
                          ↓
Claude ──► MCP Server + Bearer token ──► Token validated locally (JWT) ──► Request proceeds
```

Step by step:

1. Claude attempts an MCP call without a token → MCP server returns `401 Unauthorized` with a `WWW-Authenticate` header pointing to VizzHub's Protected Resource Metadata (`.well-known/oauth-protected-resource`)
2. Claude discovers VizzHub's authorization endpoint and redirects the user to it
3. VizzHub redirects to Google OAuth SSO (the existing login flow)
4. User authenticates with Google → VizzHub receives the Google identity
5. VizzHub maps the Google identity to the internal VizzHub user, loads their role and permissions
6. VizzHub issues a JWT access token (scoped to the user's permissions) and a refresh token
7. Claude includes the access token as `Bearer` in all subsequent MCP calls
8. The MCP server validates the JWT locally (signature, expiration, audience) and extracts permissions from claims

### Token Strategy

| Token              | TTL                        | Validation                    | Purpose                                                                                        |
| ------------------ | -------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------- |
| Access token (JWT) | **2 hours**                | Local (signature + claims)    | Authenticates each MCP request. Short-lived enough that revocation lag is acceptable.          |
| Refresh token      | 30 days (or until revoked) | Server-side (database lookup) | Renews access tokens without re-authentication. Revoked immediately when a user is offboarded. |

**Revocation scenario:** When a user leaves the organization and their Google account is deactivated:

1. VizzHub revokes their refresh token in the database (can be automated via Google Workspace event hooks or manual admin action)
2. The current access token remains valid for up to 2 hours (worst case)
3. When it expires, the refresh attempt fails → session terminates
4. The user cannot re-authenticate because their Google account is deactivated

This provides a practical balance: no per-request introspection overhead, with a maximum 2-hour window on revocation. For a security incident requiring instant revocation, tokens can be added to a lightweight blacklist (Redis or in-memory cache) that the MCP server checks on each request.

### Permission Model

The JWT access token carries the user's VizzHub permissions as claims:

```json
{
  "sub": "user_uuid",
  "email": "miguel@vizzuality.com",
  "name": "Miguel",
  "iss": "vizzhub",
  "aud": "vizzhub-mcp",
  "exp": 1743700800,
  "iat": 1743693600,
  "permissions": {
    "iso": { "read": true, "write": true },
    "tracker": { "read": true, "write": true },
    "scorecard": { "read": true, "write": false },
    "capacity": { "read": true, "write": true },
    "playbook": { "read": true, "write": true }
  },
  "projects": ["acorn", "floodwise", "cams2_54a"]
}
```

The MCP server checks these claims before executing any tool call:

- `iso.get_document_rows()` → requires `iso.read`
- `tracker.get_project_detail("acorn")` → requires `tracker.read` AND `"acorn"` in `projects`
- `iso.create_row()` → requires `iso.write` (additionally routed through command queue)
- Insufficient permissions → `403 Forbidden`

This means the same RBAC model used in VizzHub's UI governs MCP access. No separate permission configuration needed.

### MCP Server Endpoints (OAuth Infrastructure)

The MCP server must expose the following standard OAuth endpoints:

```
GET  /.well-known/oauth-protected-resource  → Points to VizzHub as authorization server
```

VizzHub (as authorization server) must expose:

```
GET  /.well-known/oauth-authorization-server  → Authorization server metadata (RFC 8414)
GET  /oauth/authorize                          → Authorization endpoint (redirects to Google SSO)
POST /oauth/token                              → Token endpoint (issues/refreshes JWT)
POST /oauth/revoke                             → Token revocation endpoint (RFC 7009)
```

### Command Queue Attribution

The `command_transactions` table links to the authenticated user, not just a generic Claude session:

```sql
CREATE TABLE command_transactions (
  ...
  requested_by_user  UUID REFERENCES users(id),  -- VizzHub user from JWT "sub" claim
  session_id         TEXT,                         -- Claude session (for traceability)
  ...
  reviewed_by_user   UUID REFERENCES users(id),  -- User who approved/rejected
  ...
);
```

This provides full audit attribution: "proposed by Miguel (via Claude), approved by Miguel (via VizzHub UI)" or "proposed by Miguel (via Claude), approved by Elena (via MCP chat)".

## Command Queue Architecture

### Data Model

#### `command_transactions` table

Groups related commands that must be reviewed and executed as a unit.

```sql
CREATE TABLE command_transactions (
  id            UUID PRIMARY KEY,
  context       TEXT,           -- e.g. "Management Review Report Q1 2026 generation"
  requested_by  UUID REFERENCES users(id),  -- VizzHub user from JWT "sub" claim
  session_id    TEXT,           -- Claude session identifier (for traceability)
  status        TEXT DEFAULT 'pending',  -- pending | approved | rejected | executed | failed
  created_at    TIMESTAMPTZ,
  reviewed_by   UUID REFERENCES users(id),  -- VizzHub user who approved/rejected
  reviewed_at   TIMESTAMPTZ
);
```

#### `command_queue` table

Individual commands within a transaction.

```sql
CREATE TABLE command_queue (
  id              UUID PRIMARY KEY,
  transaction_id  UUID REFERENCES command_transactions(id),
  order_index     INTEGER,       -- execution order within transaction
  module          TEXT,          -- iso | tracker | scorecard | capacity | playbook
  action          TEXT,          -- iso: create_row, update_row | tracker: log_time, update_budget_line | etc.
  target          TEXT,          -- iso: document_id | tracker: project_id | playbook: article_id | etc.
  payload         JSONB,        -- action-specific data
  ref_alias       TEXT,          -- e.g. "nc_new" for cross-referencing
  status          TEXT DEFAULT 'pending',
  result          JSONB,        -- populated after execution
  executed_at     TIMESTAMPTZ,
  error           TEXT           -- populated if execution fails
);
```

### Cross-referencing Between Commands (Saga Pattern)

When commands within a transaction depend on each other (e.g., a corrective action referencing a nonconformity), use `ref_alias` and `$ref` syntax:

```json
{
  "transaction_id": "txn-001",
  "commands": [
    {
      "order_index": 1,
      "action": "create_row",
      "target_document": "nonconformities",
      "ref_alias": "nc_new",
      "payload": { "Description": "...", "Severity": "Major" }
    },
    {
      "order_index": 2,
      "action": "create_row",
      "target_document": "corrective_actions",
      "payload": {
        "nonconformity_ref": "$nc_new.id",
        "responsible": "Miguel",
        "due_date": "2026-05-15"
      }
    }
  ]
}
```

On execution, the Command Service resolves `$nc_new.id` with the actual ID returned by the first command. If any command fails, all previous commands in the transaction are rolled back.

### Request Flow

```
Claude ──► MCP ──► Command Service ──┬── READ?  ──► VizzHub API (direct)
                                     │
                                     └── WRITE? ──► command_queue table ──► VizzHub UI (approval) ──► VizzHub API
```

The Command Service is a middleware layer between the MCP server and the VizzHub API. It inspects each operation and routes it accordingly. The existing VizzHub API requires no changes.

### Approval Flow

There are two complementary approval paths:

1. **Conversational (via MCP):** Claude calls `get_pending_commands()`, presents them to the user, and on explicit confirmation calls `approve_command(id)`. Best for supervised sessions where the user is actively working with Claude.

2. **VizzHub UI (fallback):** A "Pending Actions" inbox in VizzHub displays all queued commands with approve/reject buttons. Best for async review, batch approval, or when a different team member should authorize.

Both paths update the same `command_queue` table and produce the same audit trail.

## Audit Trail

Every command in the queue serves as an audit log entry. The combination of `command_transactions` and `command_queue` provides:

- **What** was proposed (action, target, payload)
- **Why** it was proposed (context field, linked to the generating process)
- **Who** requested it (session_id → Claude session)
- **When** it was proposed and executed (timestamps)
- **Who** approved it (reviewed_by → VizzHub user)
- **What happened** (result or error)

This is directly useful for ISO 27001 and ISO 9001 audits when demonstrating AI governance and change control.

## Implementation Phases

### Phase 1: Read-Only MCP (ISO)

- Implement `iso.get_records()` and `iso.get_document_rows(document_id, period)`
- Build the MCP server connecting to the existing VizzHub API
- Create the Management Review Report skill that uses these endpoints
- Validate the end-to-end flow: Claude reads records → generates report

### Phase 2: Read-Only MCP (Relational Modules)

- Add Tracker read endpoints: `tracker.get_projects()`, `tracker.get_project_detail()`, `tracker.get_time_entries()`, `tracker.get_budget_summary()`
- Add Scorecard read endpoints: `scorecard.get_scorecards()`, `scorecard.get_scorecard_detail()`, `scorecard.get_indicator_history()`
- Add Capacity read endpoints: `capacity.get_team_availability()`, `capacity.get_project_allocations()`, `capacity.get_utilization()`
- Add Playbook read endpoints: `playbook.get_articles()`, `playbook.get_article()`, `playbook.search_articles()`
- Validate cross-module queries (e.g., project health combining Tracker + Scorecard data)

### Phase 3: Command Queue + Permission Layer

- **Permission layer (prerequisite):** Add `McpUserContext` (ContextVar) propagating JWT claims (user_id, roles, permissions) to all tools. In HTTP mode, set from auth middleware; in stdio mode, grant full access. Each data module enforces its own restrictions (ISO: `USER_VISIBLE_ROOT_SLUGS` for non-editors; others: pass-through initially, prepared for future restrictions). Retroactively applies to all Phase 2 read tools.
- Add `command_queue` and `command_transactions` tables
- Implement the Command Service middleware — checks write permissions before queuing
- Add write operations for ISO (`iso.create_row`) routed through queue
- Build the "Pending Actions" inbox in VizzHub UI
- Add `get_pending_commands()`, `approve_command()`, `reject_command()` to MCP
- Extend write operations to relational modules (Tracker, Capacity, Playbook)

### Phase 4: Transactions

- Add `ref_alias` / `$ref` resolution in the Command Service
- Implement transactional execution with rollback
- Group related commands in the VizzHub approval UI

### Phase 5: Policy Engine (Optional)

- Configurable rules for which operations require approval vs. pass-through
- Risk-based routing: low-risk writes (e.g., logging time, adding a comment) skip the queue
- Role-based approval (certain documents or modules require specific approvers)

## Skill Integration

Skills encode domain knowledge for specific tasks that consume VizzHub data via MCP. Each skill knows what data it needs and how to structure the output.

### Example Skills

**`management-review-report`** (ISO)

- Knows which sections the Management Review Report requires per ISO 9001 clause 9.3 and ISO 27001 clause 9.3
- Uses `iso.get_records()` to discover available registers and match them to report sections
- Calls `iso.get_document_rows()` for each relevant register
- Synthesizes data into the report structure with analysis, trends, and recommendations
- Proposes follow-up actions (action items, nonconformities) via the command queue when gaps are identified

**`project-health-report`** (Tracker + Scorecard + Capacity)

- Pulls budget vs. actuals from Tracker, performance scores from Scorecard, and team allocation from Capacity
- Cross-references to identify projects that are over-budget, under-resourced, or underperforming
- Generates a unified project health summary

**`capacity-planning`** (Capacity + Tracker)

- Reads current allocations and upcoming project timelines
- Identifies over/under-allocation and scheduling conflicts
- Proposes allocation adjustments via the command queue

**`iso-audit-prep`** (ISO + cross-module)

- Aggregates all ISO records for a given period
- Cross-references with Tracker (were audit actions budgeted?) and Capacity (are responsible parties available?)
- Produces audit-ready documentation packages

Skills contain domain knowledge (what the output needs), not implementation knowledge (what tables or registers exist). The MCP's self-describing endpoints (`iso.get_records()`, semantic tool descriptions for relational modules) bridge the gap.

## Key Design Decisions

1. **Two-tier API reflecting two data models:** The ISO module gets a generic `get_records()` / `get_document_rows()` API matching its flexible spreadsheet-like schema. Relational modules (Tracker, Scorecard, Capacity, Playbook) get semantic domain-specific endpoints matching their stable, well-defined data models. This avoids forcing either model into the other's paradigm.

2. **Queue over direct write — all modules:** All write operations across all modules go through the command queue. No exceptions in the initial implementation. Simplifies the security model and audit story. The `module` field on each command routes execution to the correct API.

3. **Command Service as middleware:** The existing VizzHub API is untouched. The Command Service sits between MCP and the API, routing reads directly and writes through the queue.

4. **Dual approval paths:** Conversational (via MCP in chat) and async (via VizzHub UI). Same underlying mechanism, different UX for different contexts.

5. **Self-describing catalogue for ISO:** `iso.get_records()` with descriptions makes the ISO module discoverable. New registers don't require MCP or skill updates. Relational modules are discoverable through their explicit tool descriptions in the MCP server definition.

6. **Cross-module skills:** The MCP exposes all modules through a single server, enabling skills that combine data from multiple modules (e.g., a project health report pulling from Tracker, Scorecard, and Capacity simultaneously). This is where the platform approach pays off versus module-specific integrations.
