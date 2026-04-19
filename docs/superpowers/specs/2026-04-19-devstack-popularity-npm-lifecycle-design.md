# DevStack — Popularity metrics + npm lifecycle

**Date:** 2026-04-19
**Module:** `devstack`
**Status:** Approved, pending implementation plan

## Goal

Add two sets of signals to the DevStack catalog so that admins and the sync contract have empirical data about entry health and adoption:

1. **Popularity** — anonymous aggregate install counter per entry.
2. **npm lifecycle** — vulnerabilities (GitHub Advisory DB) and deprecation status (npm registry) for entries with `install_method: npm`.

Both surface in the UI (catalog + detail) and in the MCP `devstack_get_catalog` projection. No CLAUDE.md re-deploy required.

## Non-goals

- **Per-user tracking.** Intentionally out of scope; anonymous aggregate is enough for admin decisions (zombies, organic hits, `required` adoption). Reconsider if a concrete per-user use case emerges.
- **Forcing the sync contract to warn about vulnerabilities.** Data is exposed; UX in the managed CLAUDE.md is evaluated later once we see how the signals are used.
- **npm stale / last-release tracking (option C).** Too much noise without context.
- **External popularity via npm downloads (option D).** Low signal for our mostly-private catalog.

## Architecture

### Schema

Six new columns on `devstack_entries`:

| Column | Type | Default | Notes |
|---|---|---|---|
| `install_count` | `int NOT NULL` | `0` | Incremented on each successful `get_installable` call. |
| `last_installed_at` | `timestamptz NULL` | — | `now()` on each `get_installable` success. |
| `deprecated` | `bool NOT NULL` | `false` | From `npm view <pkg> deprecated`. |
| `deprecation_message` | `text NULL` | — | The deprecation string, when present. |
| `vulnerabilities` | `jsonb NULL` | — | `{critical, high, moderate, low, advisories: [{id, severity, title, url}]}`. |
| `vulnerabilities_checked_at` | `timestamptz NULL` | — | Last time the cron refreshed CVE data. |

One Alembic migration. No asyncpg-enum gotcha (all built-in types).

### Backend

**`mcp_server/data/devstack.py`** — `get_installable`:
- After `fetch_github_content` returns non-None, run a single update:
  ```sql
  UPDATE devstack_entries
  SET install_count = install_count + 1,
      last_installed_at = now()
  WHERE id = :id
  ```
- On failure to increment (e.g., DB error), log and return content anyway — tracking must not block installs.

**`app/modules/devstack/services/npm_version.py`** — extend `fetch_npm_latest` (or add sibling `fetch_npm_deprecation`) to read `deprecated` from the `npm view` JSON output. Keep API-shape minimal: return `(latest_version, deprecation_message | None)`.

**New: `app/modules/devstack/services/npm_security.py`**:
```python
async def fetch_npm_advisories(package: str, version: str, token: str) -> dict
```
- Calls `GET https://api.github.com/advisories?ecosystem=npm&affects=<pkg>@<ver>&per_page=100` (paginated if needed).
- Reuses the existing GitHub integration token (same one `github_sha.py` uses).
- Parses response into `{critical, high, moderate, low, advisories: [{id, severity, title, url}]}`.
- Returns `None` on HTTP error (caller decides how to persist).

**`app/modules/devstack/services/sha_refresh.py`** — extend the existing daily cron to also:
- For each active entry with `install_method == "npm"` and `package`:
  - Call `fetch_npm_latest` + read deprecation in the same call (already fetches JSON).
  - Call `fetch_npm_advisories(package, package_version, token)`.
  - Update `deprecated`, `deprecation_message`, `vulnerabilities`, `vulnerabilities_checked_at` in one UPDATE.
- GitHub entries skip the npm branches; their existing SHA refresh is unchanged.

### Data flow on install

```
MCP client (Claude Code session)
  → devstack_get_installable(name)
    → fetch_github_content(url, token)           # succeeds
    → UPDATE install_count + last_installed_at   # fire-and-log-errors
  ← { target_path, content }                     # client writes to disk
```

If `fetch_github_content` fails, no counter increment (correct — install didn't happen).
If the client fails to write the returned content, we overcount by 1 — acceptable.

### Frontend

**`EntryCard.tsx`** (catalog grid card):
- Red badge `"{n} critical"` / `"{n} high"` when `vulnerabilities.critical > 0` or `vulnerabilities.high > 0` (prefer critical; stack if both).
- Amber badge `"deprecated"` when `deprecated: true`.
- Install count chip `↓ {install_count}` next to the existing star/featured row. Hide when `install_count === 0`.

**`EntryDetail.tsx`** (entry detail page):
- New section **"Security"** visible only when `vulnerabilities?.advisories.length > 0`: list of advisories with severity badge, title, and link to the GitHub Advisory.
- Amber banner when `deprecated: true`, showing `deprecation_message`.
- Metadata row: `Installed {install_count} times` · `Last install: {relative time}`.

**`Catalog.tsx`**:
- Add `"Most installed"` option to the existing sort dropdown. Default remains unchanged.

### Types

- `frontend/src/modules/devstack/types/devstack.ts` — extend `DevstackEntry` with the new fields.
- `backend/app/modules/devstack/schemas.py` — extend `EntryResponse`.
- `mcp_server/data/devstack.py::_CATALOG_FIELDS` — add `install_count`, `last_installed_at`, `deprecated`, `deprecation_message`, `vulnerabilities`.
- `_DISCOVER_FIELDS` unchanged.

## Why this design

**Anonymous aggregate over per-user:** the use case that justified per-user (populating a My Environment page) no longer exists — that page was removed. The questions we actually want to answer (zombies, organic hits, `required` adoption) are all answerable with aggregates, and we skip the privacy decision entirely.

**Increment inside `get_installable` (not a separate endpoint):** the sync contract in the managed CLAUDE.md is already deployed. A new endpoint would require re-deploying Miradore to all 30 devs and would still depend on the LLM remembering to call it. Counting `get_installable` calls is close enough — we're measuring "interest expressed through the catalog", which is the right metric for catalog health.

**GitHub Advisory DB over `npm audit`:** `npm audit` needs a `package.json`; the Advisory DB works on `(package, version)` directly. Same auth we already use (GitHub token). Public and rate-limited at 5000/hr for authenticated calls — plenty for ~50 npm entries daily.

**Contract unchanged in v1:** we don't want to push warning behavior into the LLM before we see how admins use the data. Ship the signal, iterate the UX later.

## Risks

- **Overcounting on client write failure.** Noted. Negligible for the questions we're asking.
- **GitHub Advisory API shape changes.** The fetch layer returns `None` on any parse error → `vulnerabilities` becomes stale rather than corrupt. Tests pin the shape.
- **`npm view` output format changes.** Already a dependency; extending it by one field is low-risk. Existing tests cover the happy path.
- **Cron duration grows.** With ~50 entries and 2 extra HTTP calls per npm entry, upper bound is ~30s more. No scheduling conflict.

## Testing

- **Unit:** `get_installable` increments counter on success; does not on fetch failure. Advisory parser handles empty list, single severity, multiple severities, missing fields. `npm view` parser reads deprecation field.
- **Integration:** cron updates both npm + vulnerability fields for an npm entry; skips github entries.
- **Frontend:** EntryCard renders badges correctly for each vuln/deprecated state. Sort option updates the list order.

## Rollout

- One Alembic migration — auto-applied on deploy.
- No data backfill needed; `install_count` starts at 0, vulnerability fields populated by first cron run post-deploy.
- No Miradore re-deploy, no CLAUDE.md change, no MCP client disruption.
