# MCP Permission Layer Design

Phase 3 prerequisite: propagate JWT user identity to all MCP tools and enforce
module-level access control + data-level filtering.

## Problem

The MCP server issues JWTs with `roles` and `permissions` claims during OAuth,
but `VizzHubTokenVerifier.verify_token()` returns the SDK's `AccessToken` model
which only carries `token`, `client_id`, `scopes`, and `expires_at`. The claims
are decoded and then discarded. No tool or data function knows who is calling it.

Concrete gaps today:
- ISO registries are visible to all authenticated users (should require ISO editor role)
- ISO documents are unfiltered (non-editors should only see policies + procedures)
- No audit trail of which user invoked which tool (only `client_id`)
- Future write tools (Phase 3B command queue) need a user to attribute commands to

## Design

### 1. McpUserContext dataclass

Lives in `mcp_server/data/base.py` alongside the existing `_session_override` ContextVar.

```python
from dataclasses import dataclass, field
from contextvars import ContextVar

@dataclass(frozen=True)
class McpUserContext:
    user_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, action: str) -> bool:
        return "*" in self.permissions or action in self.permissions

FULL_ACCESS = McpUserContext(
    user_id="stdio",
    email="local",
    roles=["admin"],
    permissions=["*"],
)

_mcp_user_context: ContextVar[McpUserContext | None] = ContextVar(
    "_mcp_user_context", default=None
)
```

`frozen=True` prevents accidental mutation. `FULL_ACCESS` is used in stdio mode.

### 2. Helpers

Same file (`mcp_server/data/base.py`):

```python
def get_mcp_user() -> McpUserContext:
    ctx = _mcp_user_context.get()
    if ctx is None:
        raise RuntimeError("MCP user context not set")
    return ctx

def set_mcp_user(ctx: McpUserContext) -> None:
    _mcp_user_context.set(ctx)
```

Test helper (context manager, follows `override_session` pattern):

```python
@asynccontextmanager
async def override_mcp_user(ctx: McpUserContext):
    token = _mcp_user_context.set(ctx)
    try:
        yield
    finally:
        _mcp_user_context.reset(token)
```

### 3. ContextVar injection — where and when

**HTTP mode (production):** `VizzHubTokenVerifier.verify_token()` already decodes
the full JWT payload. After decoding, it calls `set_mcp_user()` with the claims
before returning the `AccessToken`. This happens once per request, before any
tool executes.

```python
# token_verifier.py — inside verify_token(), after jwt.decode()
from mcp_server.data.base import McpUserContext, set_mcp_user

set_mcp_user(McpUserContext(
    user_id=payload.get("sub", "unknown"),
    email=payload.get("email", ""),
    roles=payload.get("roles", []),
    permissions=payload.get("permissions", []),
))
```

No second decode. No cache dict. The ContextVar is scoped to the async task
that handles the request — it's garbage collected when the request ends.

**Stdio mode (local dev):** `mcp_server/__main__.py` sets `FULL_ACCESS` before
starting the server. All tools see admin-level permissions.

```python
from mcp_server.data.base import FULL_ACCESS, set_mcp_user

def main() -> None:
    set_mcp_user(FULL_ACCESS)
    mcp.run(transport="stdio")
```

### 4. Tool-level gating

A decorator that checks broad module-level permissions before the tool runs.

Lives in a new file `mcp_server/auth/permissions.py`:

```python
import functools
from mcp_server.data.base import get_mcp_user

def mcp_requires(permission: str):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            user = get_mcp_user()
            if not user.has_permission(permission):
                return json.dumps({
                    "error": f"Permission denied: requires {permission}",
                    "user": user.email,
                })
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
```

Returns a JSON error (not an exception) so the MCP client gets a readable
message. Applied at function definition (before registration on FastMCP):

```python
@mcp_requires("tracker:view")
async def tracker_get_projects(status: str | None = None, ...) -> str:
    ...
```

`functools.wraps` preserves `__wrapped__`, which `inspect.signature()` follows
to read the original typed parameters. FastMCP uses `inspect.signature()` for
schema generation, so the decorator is transparent to tool registration.

#### Permission mapping

| Tools | Gate | Rationale |
|---|---|---|
| `tracker_*` (7 tools) | `tracker:view` | All users with `user` role have this |
| `scorecard_*` (4 tools) | `scorecard:view` | All users with `user` role have this |
| `capacity_*` (4 tools) | `tracker:view` | Capacity is analytical view of tracker data; no dedicated `capacity:view` action exists. All users with `user` role have `tracker:view`. |
| `iso_get_registries` | `iso_docs:edit` | Registries are internal compliance records |
| `iso_get_registry_rows` | `iso_docs:edit` | Same — compliance data, not public |
| `iso_get_documents` | *(authenticated only)* | Data-level filtering handles visibility |
| `iso_get_document` | *(authenticated only)* | Data-level filtering handles visibility |
| `iso_search_documents` | *(authenticated only)* | Data-level filtering handles visibility |
| `playbook_*` (3 tools) | *(authenticated only)* | Visible to all team members |
| `users_*` (4 tools) | *(authenticated only)* | Team directory, visible to all |

"Authenticated only" = the `get_mcp_user()` call inside the tool will raise
`RuntimeError` if no context is set, which is sufficient — in HTTP mode this
can only happen if token verification failed (which the SDK blocks before
reaching tools).

#### Capacity permission note

There is no `capacity:view` action in the backend. Capacity insights are an
analytical cross-module view built from tracker data. We gate on `tracker:view`
which every `user` role has. If a dedicated capacity permission is added in the
future, the gate updates in one place.

### 5. Data-level filtering — ISO documents

The backend's `deps.py` defines `USER_VISIBLE_ROOT_SLUGS = {"policies", "procedures"}`
and a `get_visible_node_ids()` function that resolves the full subtree. The MCP
data layer needs equivalent filtering.

**Approach:** Import the allowlist from the backend. The MCP data layer already
imports backend models (`PYTHONPATH=backend`), so importing a constant is
consistent.

Affected functions in `mcp_server/data/iso.py`:

#### `get_documents()`

Add a `visible_categories` parameter. When the user lacks `iso_docs:edit`,
filter to documents whose category root slug is in `USER_VISIBLE_ROOT_SLUGS`.

The backend implementation uses `get_visible_node_ids()` which walks the tree
to find all node IDs under the allowed roots. For the MCP layer we can use
the simpler approach of filtering by the document's **root ancestor slug**,
since the doc query already joins through the node tree.

Implementation: add a CTE or subquery that walks up to the root node for each
document and filters by `root.slug IN ('policies', 'procedures')`. Alternatively,
join with a recursive CTE that finds descendants of the allowed roots (same
approach as `get_visible_node_ids` but in SQL).

The choice between approaches is an implementation detail — the requirement is:
when the user lacks `iso_docs:edit`, only return documents under the `policies`
and `procedures` root groups.

#### `get_document()`

Same filter: if the requested slug is not under an allowed root, return
`{"error": "Document not found"}` (not "permission denied" — don't leak
that the document exists).

#### `search_documents()`

Same filter applied to the full-text search CTE: only include results from
documents under allowed roots.

#### Registries — no data-level filtering needed

Registries are gated at tool level (`iso_docs:edit` required). If you pass
the gate, you see all registries. No per-registry visibility rules exist today.

### 6. Files changed

| File | Change |
|---|---|
| `mcp_server/data/base.py` | Add `McpUserContext`, `FULL_ACCESS`, ContextVar, `get_mcp_user()`, `set_mcp_user()`, `override_mcp_user()` |
| `mcp_server/auth/token_verifier.py` | Call `set_mcp_user()` after JWT decode |
| `mcp_server/auth/permissions.py` | **New file.** `mcp_requires()` decorator |
| `mcp_server/__main__.py` | Set `FULL_ACCESS` before `mcp.run()` |
| `mcp_server/tools/iso.py` | Add `@mcp_requires("iso_docs:edit")` to registry tools; pass user context to doc tools |
| `mcp_server/tools/tracker.py` | Add `@mcp_requires("tracker:view")` to all tools |
| `mcp_server/tools/scorecard.py` | Add `@mcp_requires("scorecard:view")` to all tools |
| `mcp_server/tools/capacity.py` | Add `@mcp_requires("tracker:view")` to all tools |
| `mcp_server/tools/playbook.py` | No decorator (authenticated only) |
| `mcp_server/tools/users.py` | No decorator (authenticated only) |
| `mcp_server/data/iso.py` | Add visibility filtering to `get_documents`, `get_document`, `search_documents` |
| `mcp_server/tests/conftest.py` | Add `mcp_user` fixture with `override_mcp_user` |
| `mcp_server/tests/test_permissions.py` | **New file.** Tests for tool gating + ISO data filtering |

### 7. Permission inheritance

The MCP layer has **no permission definitions of its own**. It reads whatever
the JWT carries, which is populated by the backend's `resolve_permissions()`
during the OAuth callback. The chain:

```
roles.py (ROLE_PERMISSIONS) → resolve_permissions() → JWT claims → McpUserContext
```

If the backend changes role-to-permission mappings (e.g., removes `tracker:view`
from the `user` role), the next JWT issued will reflect that, and MCP tool gates
will enforce it automatically. No MCP-side configuration needed.

This means the current mapping table ("all users have `tracker:view`") reflects
today's role definitions. As the backend evolves to more granular access, the
MCP layer follows without code changes — only the `@mcp_requires` value on each
tool determines what permission string is checked.

### 8. What does NOT change

- No new database tables
- No new backend permissions/roles/actions
- No UI changes
- No changes to the OAuth flow or JWT payload structure
- Modules without restrictions (playbook, users) only validate authentication
- Existing tool signatures unchanged — the decorator is transparent

### 9. Test strategy

#### Tool-level gating tests (`test_permissions.py`)

For each gated module, test two scenarios:
1. **User with required permission** → tool returns data normally
2. **User without required permission** → tool returns JSON error with `"Permission denied"`

Use `override_mcp_user()` to inject different permission sets without real JWTs.

#### ISO data-level filtering tests

1. **ISO editor** calls `iso_get_documents` → sees all categories
2. **Regular user** calls `iso_get_documents` → sees only policies + procedures
3. **Regular user** calls `iso_get_document("some-internal-plan-slug")` → gets "not found"
4. **Regular user** calls `iso_search_documents("encryption")` → results filtered to visible docs
5. **Regular user** calls `iso_get_registries` → permission denied (tool-level gate)

#### Token verifier integration test

1. Decode a valid JWT with known roles/permissions
2. Verify `get_mcp_user()` returns matching `McpUserContext`
3. Verify the returned `AccessToken` still works for the SDK

#### Stdio mode test

1. Verify `get_mcp_user()` returns `FULL_ACCESS` when set in `__main__`

### 10. Edge cases

**User with no roles:** JWT is valid (authenticated) but `permissions` is empty.
They can call playbook/users tools (no gate) but fail on tracker/scorecard/capacity/ISO.
This is correct — a user with no roles should have minimal access.

**Admin user (`"*"` permission):** `has_permission()` checks for `"*"` first —
admins pass all gates. This matches the backend behavior.

**Token verifier called multiple times:** The ContextVar is set each time
`verify_token()` runs. In the MCP SDK's SSE transport, `verify_token()` is
called once per message. The ContextVar is set fresh — no stale state.

**Concurrent requests (HTTP mode):** Each async task has its own ContextVar
copy. Two simultaneous requests from different users don't interfere.
