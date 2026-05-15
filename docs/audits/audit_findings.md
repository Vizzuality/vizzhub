# Audit Findings

Consolidated output from `audit_tech_debt.md` and `audit_calculations.md`. Each iteration appends new findings; items are then classified as [warning] / [won't do] / [fixed] and bucketed below.

---

## Status (2026-05-15 PM)

**109 fixed · 18 won't do · 136 warning.** Full backend (1843) + frontend (433) test suites pass on a clean run. Tier 1 + Tier 2 priority pass closed; previously-deferred "disabled governance tool" UX item now landed. The remaining 136 warnings are real but legitimately deferred technical debt — attack them via the boy-scout rule (touch a file, fix its warnings in the same PR), not via dedicated sweeps.

**3 items have been promoted to "High priority — attack first" below**: they are not catastrophic today, but each has a failure mode that becomes silent or unrecoverable in the next change to its area. Address them before the next boy-scout pass through the same files.

---

## High priority — attack first

These three remained `[warning]` for scope reasons but stand out from the rest: each is "safe today, dangerous on the next change to this area". Order is by blast radius if not fixed.

### HP-1. MCP permission gating is invisible in CI

**File:** `mcp_server/data/base.py:41-46`, all MCP tests.
**Risk class:** silent regression on auth surface.

`FULL_ACCESS = McpUserContext(permissions=["*"])` is the default test user. Every MCP test that doesn't explicitly override it passes every `@mcp_requires` gate. **The day someone removes a `@mcp_requires` decorator on a write tool, CI stays green** — the regression has no test that would fail. Combined with HP-2 below, the audit trail for the change would also be silent.

**Fix (~30 min):**
1. Add a `restricted_user` fixture: `McpUserContext(permissions=["iso_docs:view"])`.
2. For each write tool (iso_*, playbook_*), add one test that calls it with `restricted_user` and asserts the gate raises / blocks.
3. Optionally invert the default: `FULL_ACCESS` fixtures must be opted into explicitly; default = `restricted_user`. (Bigger change; do as follow-up.)

Added: 2026-05-14 by audit_tech_debt iteration #15. Promoted to HP: 2026-05-15.

---

### HP-2. `mcp_requires` denials look like successful tool runs

**File:** `mcp_server/auth/permissions.py:11-29`.
**Risk class:** broken audit trail + LLM-agent confusion.

On permission failure the decorator returns `{"error": "..."}` as a JSON string. FastMCP treats that as a *successful* return value. The caller (LLM agent or UI) cannot distinguish "tool ran and reported a failure" from "tool was blocked at the gate". An LLM reading the denial message may decide to try an alternate route, and from the server's perspective nothing logs the access attempt as a denial.

**Fix (~10 min):** `raise ToolError(f"Permission denied: requires {permission}")`. FastMCP surfaces it as a tool error distinguishable from a return value; add a structlog event `mcp_permission_denied(tool, permission, user_id)` for the audit trail.

Added: 2026-05-14 by audit_tech_debt iteration #15. Promoted to HP: 2026-05-15.

---

### HP-3. XSS / Slack mrkdwn injection latent in two rendering paths

Two files share the same shape — *safe today by accident, unsafe the next time someone touches them*. Treat as one piece of work.

**Files:**
- `backend/app/modules/playbook/services/publish_service.py:47` — Jinja `autoescape=False`. Currently safe because markdown-it pre-renders content to sanitized HTML before Jinja sees it. The next template that adds a placeholder taking a raw string inherits the unsafe default.
- `backend/app/modules/notifications/services/alert_service.py:38` — `render_template` does `str(value)` with no Slack mrkdwn escaping. Currently safe because project/user names come from trusted DB rows. The next template that interpolates a Jira-sourced field (controlled by external users) becomes a Slack-mrkdwn injection vector.

**Risk class:** XSS / formatting injection. Low likelihood today, but the project actively adds templates and interpolations.

**Fix (~30 min each):**
- Jinja: flip `autoescape=True`; register a `safe_html` filter (or use `Markup`) for the one pre-rendered content block.
- AlertService: add `markdown_escape(value)` that escapes `*`, `_`, `` ` ``, `>`, `<`, `|`; apply to every interpolated value (or whitelist trusted fields).

Added: 2026-05-14 by audit_tech_debt iterations #7, #12. Promoted to HP: 2026-05-15.

---

## Pending — by criticality

Open `[warning]` items grouped by audit severity. Touch the file? Fix the warning in the same PR. 4 promoted to "High priority" above.

### Major (66)

- **Files exceed 400 LOC** — `backend/app/core/api/projects_v2.py` (464 LOC), `backend/app/core/api/admin_users.py` (416 LOC) [warning] — split deferred; high refactor cost vs. current value, files are cohesive CRUD modules. Revisit when adding a new concern.
  - Module: `core/api`
  - Detail: Both files mix multiple concerns: `projects_v2.py` handles CRUD + budget + milestones + links; `admin_users.py` handles user CRUD + role management + Slack sync + impersonation.
  - Fix: Split `projects_v2.py` into `projects.py` (CRUD) + `projects_budget.py` + `projects_links.py`. Split `admin_users.py` into `admin_users.py` (CRUD) + `admin_user_roles.py` + `admin_user_slack.py` + `admin_impersonation.py`.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **`capacity_insights.py` is 743 LOC — needs splitting** — `backend/app/core/services/capacity_insights.py` [warning] — split deferred; file has clear internal section markers and refactoring risks subtle JOIN bug regressions. Address when adding a 5th drill-down.
  - Module: `core/services`
  - Detail: Single file holds overview aggregation + FA detail + user detail + allocation + planner suggestion queries. Becomes hard to navigate and harder to write targeted tests against. Each drill-down level is independently testable.
  - Fix: Split into `capacity_insights/overview.py`, `capacity_insights/fa_detail.py`, `capacity_insights/user_detail.py`, with a thin `__init__.py` re-exporting public callables.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`export_service.py` is 410 LOC** — `backend/app/modules/scorecard/services/export_service.py` [warning] — code-organization-only; deferred per the same rationale as other >400 LOC findings in this audit.
  - Module: `scorecard / services`
  - Detail: Workbook construction, sheet layout, and styling all in one file. Splitting them lets us test layout without spinning up the full pipeline.
  - Fix: Extract `XLSXLayout`/`SheetBuilder` classes into a sub-package `services/export/`.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Manual-field sync between snapshot types lacks atomicity** — `backend/app/modules/scorecard/services/metrics_service.py:187-191` [warning] — sync runs inside `MetricsService.upsert_metrics`, which is already called within a request transaction (autocommit boundary commits both upserts together). A real fix would wrap with an explicit `db.begin_nested()` savepoint, but the current behavior already rolls back both on outer-transaction failure. Deferred to a savepoint refactor.
  - Module: `scorecard / services`
  - Detail: `_sync_manual_fields_to_other_snapshot()` upserts to the sibling snapshot type after the primary upsert. If the second upsert fails, we have one snapshot with the new manual value and the other with the old — exactly the bug the dual-snapshot design is supposed to prevent.
  - Fix: Move both upserts into the same transactional block; on failure, roll the whole sync back.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **`aggregation_service.py` is 434 LOC** — `backend/app/modules/tracker/services/aggregation_service.py` [warning] — code organization only; deferred.
  - Module: `tracker / services`
  - Detail: A single file holds `_valid_parts_filter`, per-FA aggregation, per-user aggregation, per-project aggregation, and the group-by validation. `_aggregate_fa_user` (L274-361) is a 90-line function with nested loops and manual grouping. The aggregation rules are the place where the most reporting bugs live; splitting and testing each axis independently buys us correctness.
  - Fix: Split into `aggregation_service/{filters.py, by_fa.py, by_user.py, by_project.py}` with a thin facade re-exporting the public API.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Broad `except Exception` returning synthetic ok=false hides real failures** — `backend/app/modules/notifications/api/slack_admin.py:149-155, 260-266`, `backend/app/modules/notifications/api/scheduled_jobs.py:196-201` [warning] — SlackService now surfaces transport / HTTP / JSON failures via structured `{ok: false, error: type}` payloads + structured logs; the outer broad `except` is now mostly redundant but kept as a safety net pending caller migration. Better: drop the broad except after migrating callers. Deferred.
  - Module: `notifications / api`
  - Detail: `test_alert` and `send_custom_notification` log via `logger.exception()` and then return `{"ok": false, "message": "..."}`. Result: the caller (UI) gets a generic "didn't work", users have no way to know whether the Slack token is invalid or our DB is down.
  - Fix: Catch the specific failure modes (`httpx.HTTPError`, `SlackAPIError`, `SQLAlchemyError`) and let everything else propagate to the global 500 handler with full traceback.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **Alert-silence enforcement has no integration test** — `backend/tests/modules/notifications/test_silences_api.py` [warning] — dedicated test-coverage sweep.
  - Module: `notifications / tests`
  - Detail: Silence CRUD is tested. There is no test that creates a silence, triggers a scheduled job (`check_dependabot_alerts`, `check_business_alerts`), and asserts the silenced alert isn't sent. A regression that bypasses `is_silenced()` would ship cleanly.
  - Fix: Add a test that wires the full path — silence row + job invocation + assertion on `SlackService.send_message` mock not being called.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **`planner.py` is 451 LOC** — `backend/app/modules/capacity/api/planner.py` [warning] — code organization only; deferred.
  - Module: `capacity / api`
  - Detail: A single file holds query building, group injection, week math (`_mondays_in_month`), upsert batch logic, and four endpoints. Splitting query and write paths makes it testable in isolation.
  - Fix: Split into `planner/{queries.py, weeks.py, writes.py, router.py}` — keep the router lean.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **Month-range parsing duplicated across capacity endpoints** — `backend/app/modules/capacity/api/insights.py:21-23`, `fa_detail.py:30-32`, `user_detail.py:39-41`, `allocation.py:24-26` [warning] — small DRY; deferred. Refactoring into a FastAPI Depends() chain has minor risk and existing helpers in `_validation.py` are already shared at function-call level.
  - Module: `capacity / api`
  - Detail: Each endpoint manually runs `parse_month` + `validate_date_range`. The shared `_validation.py` exists but isn't wired as a FastAPI dependency.
  - Fix: Expose `DateRange = Annotated[tuple[date, date], Depends(parse_and_validate_range)]` in `_validation.py` and use it on every endpoint.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **`user_detail` runs expensive JOINs without validating user_id is reportable** — `backend/app/modules/capacity/api/user_detail.py:30-37` [warning] — short-circuit validation would add another query (anti-DRY); the empty-set return is already cheap on PG with the existing indexes. Deferred.
  - Module: `capacity / api`
  - Detail: UUID format is validated, but membership in the reportable-users set is not. Non-existent or non-reportable user_ids run the full analytical query before silently returning empty.
  - Fix: Validate against the reportable-users set first; return 404 (or 422) if absent. Cache the set per-request.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **No test for write-permission denial on planner endpoints** — `backend/tests/modules/capacity/test_planner.py` [warning] — dedicated test-coverage sweep.
  - Module: `capacity / tests`
  - Detail: All tests use a `FakeUser` bypass; no test hits the real dependency chain and asserts 403 for a `user`-role principal. With write endpoints currently ungated, this regression won't be caught.
  - Fix: Add E2E permission tests via the FastAPI test client.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **Stats endpoint fires 8+ sequential DB roundtrips** — `backend/app/modules/events/services/stats_service.py:80-139` [warning] — perf-only on a low-traffic endpoint. Worth parallelizing if the dashboard becomes hot; deferred.
  - Module: `events / services`
  - Detail: `get_stats()` awaits `db.execute()` 8+ times in series (totals, attendees, costs, then group-bys for type/theme/region/year/quarter). Each round trip blocks the request worker. On warm cache the latency is "fine" but the lock-contention surface is bigger than necessary.
  - Fix: Bundle the independent reads into `asyncio.gather(*queries)`. Where possible, combine grouped aggregations into a single SELECT with `GROUPING SETS`.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **Cron snapshot path doesn't separately log review creation** — `backend/app/worker/collect_iso_snapshot.py:54-66` [warning] — symmetric review-creation log would best live in the `review_service.create_review_for_snapshot` helper; deferred to a follow-up that touches both call sites at once.
  - Module: `iso / worker`
  - Detail: Cron now creates a draft review (per recent commit `c1c652f2`), but emits only `snapshot_captured` with the review_id inlined. Memory's "cron must mirror API side effects" rule is meant for *behavior* (the side effect happens), and that's now fixed — but the *audit trail* is still asymmetric: API gets `snapshot_captured`; cron also gets `snapshot_captured` but the review-creation step has no distinct event in either path.
  - Fix: Move the review-creation log into `review_service.create_review_for_snapshot` and emit `iso_review_created` there. Both API and cron then get the event without further drift.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **`registry_rows.py` is 894 LOC** — `backend/app/modules/iso_docs/api/registry_rows.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: One file mixes list/create/update/delete + reorder + Excel export + import + copy-year + two Drive-export variants. Both the largest backend file we've audited and the one with the most distinct concerns.
  - Fix: Split into `registry_rows/crud.py`, `registry_rows/excel.py`, `registry_rows/copy_year.py`, `registry_rows/drive.py`. Keep `router.py` thin.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`drive_export_service.py` is 753 LOC** — `backend/app/modules/iso_docs/services/drive_export_service.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / services`
  - Detail: Holds OAuth refresh, Drive API retry, HTML rendering, tree walking, and the `_WalkContext` state machine. State machines without isolated tests are fragile.
  - Fix: Extract `DriveClient` (API + retry), `HtmlRenderer`, and the `_WalkContext` into separate modules with their own unit tests.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`_migrate_renamed_keys` logs a thin audit trail for cross-row data migration** — `backend/app/modules/iso_docs/api/registry_types.py:176-183` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: When a registry type's schema renames a column key, `_migrate_renamed_keys` walks every row and rewrites the data column. Today's log captures the rename map and a row count; it does not capture which registries were affected, who initiated the rename, or how many rows changed per registry. For a compliance-sensitive operation that mutates audit-relevant data in-place, that's thin.
  - Fix: Extend the log to `iso_registry_keys_renamed(type_id, type_slug, rename_map, registries_affected=[...], rows_rewritten=N, actor=user.user_id)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`delete_registry_type` blocks deletion when nodes exist but emits no log** — `backend/app/modules/iso_docs/api/registry_types.py:226-243` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: 409 returned with a list-count error detail; no structlog event. An auditor asking "why is this type still here" sees no trail of the attempts.
  - Fix: `logger.info("iso_registry_type_delete_blocked", type_id=..., node_count=..., actor=...)` before raising.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`publish_service.py` is 498 LOC** — `backend/app/modules/playbook/services/publish_service.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `playbook / services`
  - Detail: Holds the query for publishable nodes, tree building, breadcrumb computation, Jinja rendering, S3 upload, manifest writing, and orphan cleanup. State and IO mixed; hard to test the rendering path without an S3 stub.
  - Fix: Split into `publish_service/{query.py, tree.py, render.py, upload.py}` with a thin orchestrator.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **Tree-building reimplemented locally (`_build_tree`) and not delegated to `TreeService`** — `backend/app/modules/playbook/api/nodes.py:31-48` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `playbook / api`
  - Detail: `core/services/tree_service.py` is parameterized by model class for exactly this use case. ISO docs has the same problem (iteration #11). Two modules reimplementing the same tree traversal is the wrong direction.
  - Fix: Replace `_build_tree` with a `TreeService(PlaybookNodeDB).build_admin_tree(rows)` call. Same for `iso_docs`.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **No GitHub rate-limit handling on catalog/sha fetches** — `backend/app/modules/devstack/services/github_sha.py:69, 102` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / services`
  - Detail: `fetch_github_sha` and the related `fetch_github_content` make GitHub API calls without inspecting `X-RateLimit-Remaining` / `X-RateLimit-Reset` headers, and without backoff on `429 Too Many Requests`. A bulk refresh of the catalog can quietly hit the unauthenticated 60/hour limit and start failing for every dev across the org.
  - Fix: Read `X-RateLimit-Remaining` on every response; when under a small budget, switch to authenticated requests (`GITHUB_TOKEN`) if not already; on 429, parse `Retry-After` and sleep+retry once.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **No fallback when GitHub is unavailable** — `backend/app/modules/devstack/services/github_sha.py:68-78` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / services`
  - Detail: When GitHub is down or returns a non-200, `fetch_github_sha` returns `None`. The refresher then keeps the row as-is. That's fine — but there's no signal anywhere except a `devstack_sha_fetch_failed` log. A team-wide GitHub outage produces silent staleness.
  - Fix: Surface a `last_fetch_ok_at` field on the entry and expose a "stale" flag in the catalog response. When any required entry hasn't refreshed in N hours, emit a louder log (or Slack the team).
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **Broad `except Exception` swallowing context in install-tracking** — `backend/mcp_server/data/devstack.py:202` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / mcp_server`
  - Detail: A blanket catch around install logging logs and swallows everything — DB connection loss, constraint violations, network errors. We can't tell from telemetry whether install events are being persisted or silently dropped.
  - Fix: Narrow to `(SQLAlchemyError, OSError)` and re-raise unexpected errors; failing loud is fine here, install tracking shouldn't mask other failures.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **`publish_playbook_task` and `export_iso_docs_gdrive_task` are bare passthroughs with no observability** — `backend/app/worker/publish_playbook.py:10-14`, `backend/app/worker/export_iso_docs_gdrive.py:10-13` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Both tasks call the service directly with no try/except, no `job_started`/`job_completed`/`job_failed` log, and no `ScheduledJobRunDB` row. If the service raises, ARQ records "job failed" but our own audit trail is silent. For two of the longest-running, most-visible jobs in the system, that's a big gap.
  - Fix: Wrap each in the canonical pattern: create `ScheduledJobRunDB`, emit `job_started`, `try/except`, emit `job_completed` with counts or `job_failed` (use `logger.exception`).
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **`refresh_devstack_sources` task has no job-run tracking or error handling** — `backend/app/worker/refresh_devstack_sources.py:8-11` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Returns the service's raw dict, no `ScheduledJobRunDB` row, no try/except. The devstack required-entry escalation flagged in iteration #13 also depends on this telemetry being there.
  - Fix: Follow the `fetch_exchange_rates.py` pattern (create row, wrap with try/except, persist final status).
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **`check_dependabot.py` is 474 LOC; `check_business_alerts.py` is 561 LOC** — `backend/app/worker/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Two of the most complex jobs in the system, each holding `_process_project`, `_notify_*`, `_send_reminders`, and helpers in a single file. Hard to test in isolation, hard to read.
  - Fix: Split `check_business_alerts.py` into `business_alerts/{budget.py, timeline.py, overdue.py}` (or by check type). Same for `check_dependabot.py` (reminder vs new-alert paths).
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **No tests for `check_dependabot_alerts` or `check_business_alerts`** — `backend/tests/worker/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker / tests`
  - Detail: The two biggest, most failure-prone jobs in the system have zero coverage. `monthly_scorecard_capture` is the only one with a test file. Combined with the session-poisoning blocker above, that means we shipped the fix once and would never have caught the regression here.
  - Fix: Add `test_check_dependabot.py` and `test_check_business_alerts.py` with at least: happy path, `_process_project` exception → session continues, Slack 5xx handling, silence enforcement.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **`check_dependabot.py:110` increments `projects_checked` inside the try block** — `backend/app/worker/check_dependabot.py:110` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Counter increment happens after the `_process_project` call inside `try:`. If the call raises, the project is not counted. Final log under-reports both successes and failures. `check_business_alerts.py:123` increments in both branches — the convention differs between sibling files.
  - Fix: Pick one rule for both files. Recommend: increment in the except branch too (matches what `check_business_alerts.py` already does) so the count means "processed in any way".
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Long-running jobs emit no progress logs** — `backend/app/worker/monthly_scorecard_capture.py:86`, `backend/app/worker/check_dependabot.py`, the capture-history task [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: For a 100-project org, monthly capture runs for ~8 minutes (5 s sleep between projects + collector latency) with no log between start and end. If it hangs at project 73, we have no signal.
  - Fix: Inside the project loop, emit `logger.info("job_progress", job=..., done=captured, total=N)` every 10 projects or every 30 s. Keep it cheap.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Approval flow has no audit log** — `mcp_server/services/command_service.py`, `mcp_server/tools/commands.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / commands`
  - Detail: Neither file imports `logger` / `structlog`. `approve_command` and `approve_all` mutate state (command transitions from `pending` → `executed`/`failed`), but no event is emitted with `command_id`, `module`, `action`, `approved_by`, `result_status`. The human-in-the-loop guarantee that VizzHub MCP advertises is hollow without an audit trail of who approved what.
  - Fix: Add `logger.info("mcp_command_approved", command_id=..., module=..., action=..., approved_by=user.email, status=...)` immediately after the status update in `command_service.approve()` (and equivalent for `reject`). Same for `approve_all` at the loop boundary.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **No structlog on MCP tool invocations** — `mcp_server/tools/*.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / tools`
  - Detail: Tool handlers return JSON responses but never log "tool X was called by user Y with args Z". For the system that orchestrates writes-via-queue across modules, telemetry on read-side too is what lets us detect odd usage patterns or scope creep.
  - Fix: Decorator-based wrapper that emits `mcp_tool_invoked(tool=..., user=..., args_hash=...)` on entry and `mcp_tool_completed/failed` on exit. Apply via `@mcp.tool` registration so every tool gets it for free.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **No re-validation of nested JSONB fields after dequeue** — `mcp_server/handlers/iso_docs.py:295-322` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / handlers`
  - Detail: Memory documents `gotcha_mcp-jsonb-queue-types.md` — Pydantic date/Literal types stringify in the JSONB queue and the handler must re-validate. Scalar metadata fields go through `_coerce_metadata_field` correctly. But nested arrays like `changelog: list[ChangelogEntry]` flow through `_fill_changelog_authors` without re-validating each entry's four required fields against `ChangelogEntry`. A malformed entry from the queue silently persists.
  - Fix: In `_update_metadata` (~L295), call `ChangelogEntry.model_validate(entry)` for every entry before storing; on failure, raise ToolError with the entry index.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`approve_all` swallows specific failures into a generic except** — `mcp_server/tools/commands.py:188-194` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / tools / commands`
  - Detail: `except Exception as exc` rolls up validation errors, permission denials, and handler crashes into one bucket. The bulk-approve caller cannot tell why a specific command failed and which ones still need attention.
  - Fix: Catch `(ValueError, PermissionError)` distinctly, return them in a structured per-command result, and let unexpected exceptions surface to ARQ.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **No test for "approve same command twice"** — `mcp_server/tests/test_command_tools.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / tests`
  - Detail: Existing tests cover enqueue → list → approve → execute success and one denial case. Missing: idempotency of approval (calling `approve_command` twice on the same `pending` row should fail the second time cleanly, not double-execute the handler), concurrent approvals racing, and handler exception → command marked `failed` with `error_message` populated.
  - Fix: Add three targeted tests for these paths.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`ProjectForm.tsx` is 1269 LOC** — `frontend/src/core/pages/...` (ProjectForm component) [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core`
  - Detail: The largest single component in the audit so far. Holds form state, validation, budget lines, links, manager selection, currency selection, milestones, and submission. Tests on a 1200-line component are fragile and slow.
  - Fix: Split by tab/section into smaller controlled components (`ProjectFormGeneral`, `ProjectFormBudget`, `ProjectFormLinks`, etc.), with a thin shell coordinating cross-section state via a hook (`useProjectForm`).
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`JobsContent.tsx` is 643 LOC; `AlertConfigTab.tsx` is 572 LOC** — `frontend/src/core/components/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core`
  - Detail: `JobsContent` holds four section components inline (`BackgroundJobsSection`, `ScheduledJobsSection`, `PlaybookPublishSection`, `IsoDocsExportSection`). `AlertConfigTab` mixes three dialog state machines. Both are above the 400 LOC threshold and read as kitchen-sink admin pages.
  - Fix: Extract each section into its own file under `core/components/Admin/jobs/` and `core/components/NotificationsAdmin/alert-config/`. Keep the parents as thin layouts.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`useAlertDefinitions` uses raw string comparison in `predicate` invalidation** — `frontend/src/core/hooks/useAlertDefinitions.ts:79-82` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / hooks`
  - Detail: `predicate: (query) => query.queryKey[0] === 'alertDefinitions' && query.queryKey[2] === 'templates'` bypasses the `queryKeys` constant convention (memory `gotcha_react-query-undefined-key.md`). If the key shape changes, this predicate silently stops matching.
  - Fix: Either compare against `queryKeys.alertDefinitions.all[0]` (or whatever the canonical first segment is), or expose a `queryKeys.alertDefinitions.templates.partial()` matcher utility.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **Inline name-formatting in `AlertConfigTab` sort callbacks** — `frontend/src/core/components/NotificationsAdmin/AlertConfigTab.tsx:202, 238` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / components`
  - Detail: Two `localeCompare` calls inline `getFullName(a.first_name, a.last_name, a.email)` for sort. `getFullName` exists in `src/utils/formatters.ts` and is the canonical helper, but the inline duplication here is fine — the lint nit is the same expression being repeated across the file.
  - Fix: Hoist a local `displayNameOf(user)` helper at module level so the sort key is one short call.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`QualityMetricsGrid.tsx` is 474 LOC; `EditableMetricCard.tsx` is 418 LOC; `InteractiveTimelineChart.tsx` is 392 LOC** — `frontend/src/modules/scorecard/components/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard`
  - Detail: Three components above (or near) the 400 LOC threshold. `EditableMetricCard` mixes a card shell, an inline chart renderer (~L279-317), 4 callback factories, and two reference-area helpers. `QualityMetricsGrid` repeats the same `isDimensionVisible(...) → getHistoricalData(...) → render card` pattern 20+ times.
  - Fix: Extract a `MetricChartRenderer` for the chart path; lift `DIMENSION_META` to `types/index.ts`; collapse the per-metric render in `QualityMetricsGrid` into a config array + map.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Weight-sum validation only fires at save, not while editing** — `frontend/src/modules/scorecard/components/Settings/ConfigurationTab.tsx:43, 95-99`, `ParameterSection` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard`
  - Detail: `showSumValidation: true` flag exists per group but there's no live-sum badge; the user only learns the weights are off when save fails. Backend enforces `sum == 1.0` per group.
  - Fix: Render a live total next to each weight group, red when ≠ 1.0, with the delta inline. Block "Save" while invalid.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Colored badges for report status violate the dot+text rule** — `frontend/src/modules/tracker/components/ReportEditor.tsx:118-124` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / components`
  - Detail: `<Badge>` with `bg-yellow-100 text-yellow-700` (Estimated) and `bg-green-100 text-green-700` (Confirmed). CLAUDE.md and Memory explicitly say status indicators use a colored dot + plain text, never tinted pills.
  - Fix: Replace badges with the dot+text pattern used in `invoice-shared.tsx:166-177` (`<span className="inline-block w-2 h-2 rounded-full shrink-0 bg-{color}" />` + label).
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`BurnDashboard.tsx` is 565 LOC; `invoice-shared.tsx` is 534 LOC; `AdminInvoices.tsx` is 411 LOC** — `frontend/src/modules/tracker/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker`
  - Detail: Three components above the 400 LOC threshold, all in the financial UI. `BurnDashboard` holds the weighted-moving-average forecast logic — exactly the kind of code that wants a clean unit-test boundary.
  - Fix: Extract `BurnDashboard`'s `weightedMonthlyAvg` / `buildForecastPoints` to `tracker/utils/forecast.ts` with tests. Split `invoice-shared.tsx` into per-action components (`PostponeButton.tsx`, `TransitionDialog.tsx`, etc.). `AdminInvoices`: lift the table column definitions into a sibling file.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **No permission-gating tests for tracker admin pages** — `frontend/src/modules/tracker/pages/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / tests`
  - Detail: Tests currently mock the user with `permissions: ['*']`, masking permission gates. When the Major fix above migrates the gate from `ADMIN_USERS` → `TRACKER_MANAGE_ALL_REPORTS`, we want a regression test.
  - Fix: Add a "user without permission" test per admin page asserting redirect/empty/null render.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`PlannerGrid.tsx` is 854 LOC** — `frontend/src/modules/capacity/components/PlannerGrid.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity`
  - Detail: Single component holds table flattening (L354-401), week styling (L541-564), batch cell editing (L444-514), keyboard shortcuts (L470-514), selection range building (in `useCellSelection`), and rendering. The largest frontend component in the audit so far.
  - Fix: Extract a `usePlannerTable` hook for flattening + filtering; a `usePlannerBatchEdit` hook for the batch-input flow; split rendering into `PlannerHeaderRow`, `PlannerDataRow`, `PlannerAddRow`. Aim for 200-300 LOC per file.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **No tests for chart pagination, planner cell edits, batch edits, or filtered rendering** — `frontend/src/modules/capacity/components/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity / tests`
  - Detail: Tests cover `PlannerCell`, `PlannerAddRow`, allocation lists, and date utils. Missing: chart pagination boundary cases (no `<` at start / no `>` at end), planner-row filtering correctness, batch edit + selection range, optimistic update + debounced flush.
  - Fix: Add `PlannerGrid.test.tsx` with focused tests for the filter logic (the one the agent thought was wrong is actually correct — pin it down with a test before refactoring), batch-edit shortcuts, and pagination.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **Planner mutation has no error UI or retry** — `frontend/src/modules/capacity/hooks/usePlannerMutations.ts:55-114` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity / hooks`
  - Detail: `cellMutation` / `deleteMutation` use `onSettled` to invalidate the planner query — good. But on failure, the queued updates in `queueCellUpdate` are dropped silently. User sees no toast, no error indicator on the cell, and refreshing the page loses the local edit.
  - Fix: Add an `onError` to flash a toast and mark the cell as "failed" (red background) until retry. Optionally implement exponential-backoff retry in `queueCellUpdate`.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **`EventForm.tsx` is 573 LOC** — `frontend/src/modules/events/components/EventForm.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / components`
  - Detail: One file owns form state, attendee batch state, original-attendee diff, validation, delete confirmation, and submission. The delete-confirmation flow alone could live in its own component.
  - Fix: Split into `EventForm` (shell + submit), `EventFormFields`, `AttendeeSection`, `DeleteConfirmDialog`. Move form state to a `useEventFormState` hook.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **`useUpdateEvent` invalidates list but not the specific detail key** — `frontend/src/modules/events/hooks/useEvents.ts:28-29` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / hooks`
  - Detail: Mutation invalidates `queryKeys.events.all` but not `queryKeys.events.detail(id)`. If the user edits an event and stays on the detail page, the cached detail is served until it ages out. They see stale data.
  - Fix: Add `queryClient.invalidateQueries({ queryKey: queryKeys.events.detail(id) })` to the mutation's `onSuccess`.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **`StarRating` renders interactive-looking buttons when read-only** — `frontend/src/modules/events/components/StarRating.tsx:9-36`, `EventsTable.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / components`
  - Detail: Component sets `disabled={!onChange}` but keeps the same hover/cursor styles, so the read-only state looks identical to the editable one. `EventsTable` works around it by passing `onChange={() => {}}` — a no-op callback that defeats the `disabled` heuristic entirely.
  - Fix: Make read-only explicit: a `readOnly` prop that triggers `opacity-50 cursor-default` and absence of hover styles. Have `EventsTable` pass `readOnly` instead of the no-op.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **No tests for `Events.tsx` or `EventDetail.tsx`** — `frontend/src/modules/events/pages/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / tests`
  - Detail: Only `EventForm` and `EventsTable` have tests. List filtering, URL state, gating-driven affordances, and the detail page rendering are uncovered.
  - Fix: Add `Events.test.tsx` (canManage off → no Create button; year filter narrows list) and `EventDetail.test.tsx` (canManage off → no Edit button; attendee list renders empty state).
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **Hard-coded `event_type: 'Conference'` initial value** — `frontend/src/modules/events/components/EventForm.tsx:64` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / components`
  - Detail: Default value is a literal string. If `Conference` is removed from the backend options, form submission silently fails. Better to seed from the options endpoint or require an explicit selection.
  - Fix: `event_type: options?.event_types?.[0] ?? ''` once options load; mark the select required.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **Reviewer dropdown is disabled (not read-only) when signed** — `frontend/src/modules/iso/components/ReviewPanel.tsx:163` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / components`
  - Detail: `disabled={isSigned}` greys out the select after sign-off, which is the wrong affordance — it reads as "you could fix this if you wanted." For compliance, signed state should render as plain text ("Reviewed by Alice") because the field is locked, not gated.
  - Fix: Conditionally render `<span>{reviewer.name}</span>` when `isSigned`; reserve the select for the editable case (mirrors the pattern at `ActionRow.tsx:59-80`).
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **Provider data-tab state held locally instead of URL-driven** — `frontend/src/modules/iso/components/SnapshotDataTabs.tsx:238`, `GitHubDataTabs.tsx:242`, `JiraDataTabs.tsx:141` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / components`
  - Detail: Three sibling tab containers each maintain `activeTab` in `useState`. Same shape as the scorecard/tracker tab patterns — losing tab state on refresh is annoying for an admin reviewing a snapshot.
  - Fix: Lift `activeTab` to the parent (`ISOSnapshotDetail.tsx`) and bind via `useUrlState` with a single `tab` URL param.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **No tests for the sign→unsign round-trip or empty-export warning** — `frontend/src/modules/iso/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / tests`
  - Detail: `ISOSnapshotDetail.test.tsx` covers render and button visibility for signed state but does not call the sign mutation, doesn't verify the actions payload serialization, and doesn't cover unsign. No test for `useIsoExport` empty-blob detection.
  - Fix: Add (a) E2E sign→unsign test asserting payload shape on sign and state transition on unsign; (b) `useIsoExport.test.ts` mocking a tiny blob and asserting the error toast fires.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **`IsoDocs.tsx` is 898 LOC; `RegistryView.tsx` is 761 LOC** — `frontend/src/modules/iso-docs/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs`
  - Detail: Two of the three largest frontend files in the audit so far. `IsoDocs.tsx` holds tree state, node selection, content panel switching, metadata filter UI, dialogs, and three tree-utility helpers (`flattenTree`/`buildSlugMaps`/`buildReorderItems` at L61-108). `RegistryView.tsx` mixes the table, lightbox, dialogs, sorting, attachments, and column-visibility logic.
  - Fix: Split `IsoDocs` into `IsoDocsShell` (layout + tree) + `IsoDocsContent` (panel content); move tree helpers to `core/services/tree_service` (also addresses iteration #11 DRY finding). Split `RegistryView` into `RegistryTable` + `RegistryToolbar` + `RowLightbox` + `RegistryDialogs`.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **`InlineCell.tsx` is 424 LOC** — `frontend/src/modules/iso-docs/components/InlineCell.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / components`
  - Detail: One file holds display, editing, validation, attachments, conditional formatting, markdown-link parsing, and color badges. The 50-line `useInlineEditing` hook is also inlined.
  - Fix: Extract `useInlineEditing` to `hooks/useInlineEditing.ts`; extract `MarkdownLinks`/`TextOrLink`/`DisplayValue` to `components/CellDisplay.tsx`; extract `AttachmentCell` to its own file.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Tree manipulation helpers reimplemented locally** — `frontend/src/modules/iso-docs/pages/IsoDocs.tsx:61-108` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs`
  - Detail: `flattenTree`, `buildSlugMaps`, `buildReorderItems` are generic tree utilities. The playbook module (audited iteration #12) has its own copy; the shared `core/services/tree_service` exists on the backend. The frontend has no shared tree-service today.
  - Fix: Create `frontend/src/shared/services/treeService.ts` with these helpers (and the equivalents from playbook) and import from both modules. Pair with the iteration #12 minor about TreeService.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Bare string query key in registry rows hook** — `frontend/src/modules/iso-docs/hooks/useRegistryRows.ts:7` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / hooks`
  - Detail: Uses `['iso-docs', 'registry-rows', nodeId]` instead of `queryKeys.isoDocs.registryRows(nodeId, year)`. CLAUDE.md rule explicitly forbids bare-string query keys; this also breaks the centralized invalidation contract from iteration #16's nag.
  - Fix: Route through `queryKeys.isoDocs.registryRows(...)`. Add the factory if it doesn't exist.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **No tests for registry CRUD, inline edits, or schema-rename UI** — `frontend/src/modules/iso-docs/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / tests`
  - Detail: Only `NotesPanel.test.tsx` exists. RegistryView (761 LOC), InlineCell (424 LOC), and MetadataEditDialog (338 LOC) — the bulk of the module's surface — have zero coverage. Future model_fields_set fix would have no regression net.
  - Fix: Add `RegistryView.test.tsx` (5 cases minimum: create row, inline edit + save, delete with confirm, column visibility toggle, year selection), `InlineCell.test.tsx` (display modes, validation), and a test for the schema-rename migration UI.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Column-visibility toggle may not invalidate registry-type cache** — `frontend/src/modules/iso-docs/components/RegistryView.tsx:305-316` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / hooks`
  - Detail: `toggleColumn` persists via `useUpdateColumnVisibility`; if that hook doesn't invalidate `queryKeys.isoDocs.registryType(...)`, the next refetch will overwrite the user's optimistic state with the stale schema.
  - Fix: Verify `useUpdateColumnVisibility` invalidates the type query. If not, add `queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryType(registryTypeId) })` to its `onSuccess`.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **`Playbook.tsx` is 519 LOC** — `frontend/src/modules/playbook/pages/Playbook.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / pages`
  - Detail: Single component holds tree state, three dialog handlers, save/restore/publish flows, and the main content router. Reasoning about state transitions across 519 lines is painful.
  - Fix: Extract `usePlaybookHandlers` hook (save/move/delete/reorder/publish) and a `<PlaybookContent>` view component that takes the resolved page + handlers as props.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **Tree utilities redeclared locally (third module to do this)** — `frontend/src/modules/playbook/pages/Playbook.tsx:47-94` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / pages`
  - Detail: `flattenTree` / `buildSlugMaps` / `buildReorderItems` are defined locally. Iso-docs has them (iteration #23 Major). Playbook has them. The pattern is now triple-implemented across the FE.
  - Fix: Extract to `frontend/src/shared/services/treeUtils.ts` (or `core/services/`) and consume from all three modules.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`usePublishPlaybook` invalidates publish status but not tree** — `frontend/src/modules/playbook/hooks/usePublishPlaybook.ts:10` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / hooks`
  - Detail: Successful publish flips public/private state and may change tree visibility for non-editor viewers. The hook invalidates `publishStatus` only; `playbook.tree` stays stale until next refetch.
  - Fix: `queryClient.invalidateQueries({ queryKey: queryKeys.playbook.tree })` in the same `onSuccess`.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **No tests for playbook module** — `frontend/src/modules/playbook/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / tests`
  - Detail: Zero test files. The publish flow, version restore, tree reorder, max-depth validation, and conflict handling are all uncovered. Combined with the backend test gap (iteration #12), there's no regression net at either end.
  - Fix: Add `Playbook.test.tsx` (article CRUD + publish flow), `usePlaybookTree.test.ts` (tree utilities + reorder validation), and `services.test.ts` (API client mocking).
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`Required` badge color differs between EntryCard and EntryDetail** — `frontend/src/modules/devstack/components/EntryCard.tsx:39`, `frontend/src/modules/devstack/pages/EntryDetail.tsx:151` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack`
  - Detail: Card uses `bg-blue-600 text-white`; detail page uses `bg-blue-100 text-blue-800 dark:bg-blue-900`. Same semantic ("required entry"), two visual conventions in adjacent views.
  - Fix: Extract a `<RequiredBadge>` component or `BADGE_STYLES.required` constant and use in both.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **No test files for `Catalog`, `EntryDetail`, or `EntryForm`** — `frontend/src/modules/devstack/__tests__/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / tests`
  - Detail: Only `EntryCard.test.tsx` exists (79 lines). The CRUD page (`Catalog`), the detail page (`EntryDetail`), and the form (`EntryForm` 365 LOC with conditional install_method state) have no coverage.
  - Fix: Add `Catalog.test.tsx` (filter + sort + refresh button), `EntryDetail.test.tsx` (canManage rendering), `EntryForm.test.tsx` (install_method conditional rendering, validation).
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **No stale-catalog indicator on the FE** — `frontend/src/modules/devstack/pages/Catalog.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / pages`
  - Detail: Backend audit iteration #13 surfaced GitHub rate-limit, no-fallback-on-outage, and required-entry escalation gaps. The FE currently shows the catalog as if it were always fresh — no "last refresh" timestamp, no "GitHub unreachable" banner. When the BE silently returns stale rows, the user has no signal.
  - Fix: When the BE adds `last_refreshed_at` + `stale` flags (paired BE work from iteration #13), render "Updated 2m ago" / "Catalog is N minutes stale — GitHub fetch failing" near the toolbar.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **Vulnerability badge logic duplicated for critical and high severities** — `frontend/src/modules/devstack/components/EntryCard.tsx:55-64` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / components`
  - Detail: Two near-identical Tailwind className blocks for critical vs high counts; the only diff is severity name and counter prop.
  - Fix: Extract `<VulnerabilityBadge severity={...} count={...} />` and render twice (or map an array of severity definitions).
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **No tests for shared doc components consumed by Playbook + ISO Docs** — `frontend/src/shared/components/doc/*.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / shared / components`
  - Detail: `DocEditor`, `DocViewer`, `DocTree`, `NodeForm`, `VersionHistoryDialog` have zero unit tests despite being the runtime shared by both wiki modules. `useUrlState` has 8 tests — the layer's discipline on hooks isn't matched on components. The DocEditor's MDEditor remount/cursor logic (~L65-76) is exactly the surface where iteration #24's "missing key prop" bug class lives.
  - Fix: Add `DocEditor.test.tsx` (image upload + cursor position + remount semantics), `DocViewer.test.tsx` (click-interception, sanitization), `DocTree.test.tsx` (resize-observer wrapper), `NodeForm.test.tsx` (type selection).
  - Added: 2026-05-14 by audit_tech_debt iteration #26

- **`Sidebar.tsx` is 780 LOC of stock shadcn** — `frontend/src/shared/components/ui/sidebar.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / shared / ui`
  - Detail: Largest single file in the audit so far. Stock shadcn export, used by `core/components/layout/AppSidebar.tsx`. Updating shadcn upstream is hard when we've copied 780 LOC into our tree.
  - Fix: Document the file as "pristine shadcn — DO NOT EDIT" at the top, and add a script/check in CI that diffs against the upstream shadcn version on dependabot bumps. Customizations should live in a wrapper, not in this file.
  - Added: 2026-05-14 by audit_tech_debt iteration #26

### Minor (61)

- **Granular roles lack dedicated tests** — `backend/tests/core/permissions/test_roles.py` [warning] — dedicated test-coverage sweep; out of scope here.
  - Module: `core/permissions`
  - Detail: `playbook_editor`, `iso_docs_editor`, `events_manager` are defined in `ROLE_PERMISSIONS` but no test asserts their exact permission set. They only pass through the catch-all "all permissions are valid Actions" check.
  - Fix: Add `test_playbook_editor_role`, `test_iso_docs_editor_role`, `test_events_manager_role` mirroring the pattern used for manager/admin.
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **`_build_metrics_with_scores` duplicated across two endpoints** — `backend/app/modules/scorecard/api/metrics.py:24-54`, `backend/app/modules/scorecard/api/capture.py:133-155` [warning] — both helpers differ in field set (capture includes scores; metrics may include indicators-only). Worth a careful unify but risks shape regressions on existing FE consumers; deferred.
  - Module: `scorecard / api`
  - Detail: Two near-identical helpers build a `MetricsWithScores` from a DB row + computed scores.
  - Fix: Move to `scorecard/services/metrics_service.py` (or `models/__init__.py`) and re-export.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **`_consolidate_metrics` reimplements field-by-field copy that also lives in `apply_evm_fields`** — `backend/app/modules/scorecard/api/scores.py:161-185`, `backend/app/modules/scorecard/public.py:27-36` [warning] — the two helpers have meaningfully different rule sets (EVM-only vs full consolidation); unifying behind a flag is a larger refactor. Deferred.
  - Module: `scorecard`
  - Detail: Two places loop SQLAlchemy columns to copy fields, with slightly different rules. A change to either drifts.
  - Fix: Add a `MetricsDB.apply_fields(other, skip=...)` method (or a free function) and call it from both.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Resolve-end-date logic copy-pasted three ways** — `backend/app/modules/scorecard/api/metrics.py:200-205`, `backend/app/modules/scorecard/api/capture.py:240-244`, `backend/app/modules/scorecard/api/exports.py:47` [warning] — minor DRY, three implementations have subtle differences (today vs last-day-of-month). A unified helper needs careful audit of every caller's expectation. Deferred.
  - Module: `scorecard / api`
  - Detail: Three implementations of "end of month vs today" date resolution.
  - Fix: Extract `resolve_period_end(year, month, *, today_if_current=True)` to `scorecard/services/date_helpers.py` (or the existing utils).
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Weight-error message formatted for UI inside the service layer** — `backend/app/modules/scorecard/services/config_service.py:14-17` [warning] — touches the public weight-validation message contract; FE error rendering already consumes it. Worth structuring but deferred.
  - Module: `scorecard / services`
  - Detail: `_format_weight_error()` returns a user-facing sentence. The API layer should be the only place rendering strings for the UI.
  - Fix: Return a structured error (`{"type": "weight_sum", "delta": ..., "group": ...}`) and let the endpoint format.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **`_upsert_batch(include_comment)` is a flag carrying schema branching** — `backend/app/modules/capacity/api/planner.py:333-365` [warning] — minor design nit; the dual-call pattern is correct. Deferred.
  - Module: `capacity / api`
  - Detail: `include_comment` only toggles whether one dict key is added to `update_set`. The caller then splits the batch into "with comment" vs "without comment" and calls the helper twice. The flag couples two responsibilities.
  - Fix: Either always include the comment column (and let the schema decide whether the value is `None`) or split into two helpers with explicit names.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **`role: AttendeeRole` duplicated across attendee schemas** — `backend/app/modules/events/schemas/event_attendee.py:14, 19` [warning] — micro DRY, very low leverage.
  - Module: `events / schemas`
  - Detail: Same field with the same `Field(...)` in `AttendeeCreate` and `AttendeeUpdate`. Trivially DRY-able.
  - Fix: Define `RoleField = Field(..., description="Attendee role")` once and reuse.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **Stats endpoint logs nothing despite an optional `year` filter** — `backend/app/modules/events/api/stats.py:12-18` [warning] — low-value telemetry. Skipped.
  - Module: `events / api`
  - Detail: Reads only — but the `year` filter changes the shape of the response. Adding a `logger.info("event_stats_requested", year=year, user_id=...)` makes performance analysis and adoption tracking trivial.
  - Fix: Add the single log line at the top of the handler.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **`export_service.py` is 426 LOC** — `backend/app/modules/iso/services/export_service.py` [warning] — code organization only; deferred.
  - Module: `iso / services`
  - Detail: Five sheet-writer paths (users, groups, members, GitHub, Jira) plus header/diff/actions builders. Just over the 400 threshold; readable, but ripe for a split as the schema grows.
  - Fix: Extract sheet writers to `services/export/{users.py, groups.py, github.py, jira.py}` and keep `export_service.py` as a thin orchestrator.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **Per-collector `httpx.AsyncClient` setup repeated** — `backend/app/modules/iso/services/google_workspace.py:158-163`, `backend/app/modules/iso/services/collectors/github.py:191-198`, `backend/app/modules/iso/services/collectors/jira.py:205-211` [warning] — DRY micro-fix touching three live collectors with different timeout/header conventions; deferred.
  - Module: `iso / services`
  - Detail: Three collectors create a fresh `AsyncClient(timeout=30.0, headers=...)` for each capture run. Memory rule says reuse — today each capture spins up its own. Functionally fine, but the next person adding caching/retry will copy the pattern a fourth time.
  - Fix: Extract a `make_collector_client(token)` factory in `services/_http.py`.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **Tree-traversal logic in two places** — `backend/app/modules/iso_docs/api/nodes.py:36-54`, `backend/app/modules/iso_docs/api/deps.py:26-52` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: `_build_tree()` (recursive nested dict) and `get_visible_node_ids()` (iterative flat set) both walk the parent/child graph independently and rebuild `children_map`. Memory notes a shared `TreeService` in `core/services` — it isn't used here.
  - Fix: Route both call sites through `core/services/tree_service.TreeService`; if it lacks the visibility predicate, add one.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`_get_registry_node` / `_get_registry_type` private to each file** — `backend/app/modules/iso_docs/api/registry_rows.py:62-83`, `backend/app/modules/iso_docs/api/registry_types.py:34-41` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: Per-file 404 fetchers; same shape as the `core/api` finding from iteration #1.
  - Fix: Hoist into `iso_docs/api/deps.py` as `get_registry_node_or_404` / `get_registry_type_or_404`.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`_slugify` defined module-locally** — `backend/app/modules/iso_docs/api/registry_types.py:30-31` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / api`
  - Detail: Same shape as tree_service slug logic. Two copies that have to agree on edge cases (unicode, double-hyphens, leading digits).
  - Fix: Single helper in `core/utils/slugify.py` used everywhere.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`IsoDocMetadataDB.category` column is misleading (real source is parent group title)** — `backend/app/modules/iso_docs/api/metadata.py:41-48` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `iso_docs / models`
  - Detail: Memory documents this gotcha. The column persists but the API always overwrites it. A future dev reading the model will assume the column is authoritative.
  - Fix: Either rename the column (`legacy_category`) with a comment, or drop the column entirely and migrate.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **Each fetch helper builds its own `httpx.AsyncClient`** — `backend/app/modules/devstack/services/github_sha.py:69`, `backend/app/modules/devstack/services/npm_version.py:20, 39`, `backend/app/modules/devstack/services/npm_security.py:33` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / services`
  - Detail: Five distinct AsyncClient constructions; no connection pooling between sha + npm refreshes that hit the same hosts in sequence. Same shape as iso/collectors finding (iteration #10).
  - Fix: Factory in `services/_http.py` returning a shared client per host. Pair with the iso fix.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **Hardcoded GitHub org/repo for tech-radar** — `backend/mcp_server/data/devstack.py:29-32` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / mcp_server`
  - Detail: `_TECH_RADAR_REPO = "Vizzuality/vizzuality-engineering-handbook"` is a magic string. If the repo is renamed/moved, the MCP tool 404s silently (`fetch_github_content` returns None and the tool returns "tech radar unavailable").
  - Fix: Move to `settings.TECH_RADAR_REPO`; add a `/health` (or startup) check that verifies reachability.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **NPM fetch helpers log only on failure** — `backend/app/modules/devstack/services/npm_version.py`, `backend/app/modules/devstack/services/npm_security.py` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `devstack / services`
  - Detail: Successful fetches emit nothing — bulk refresh has no per-package trace, so we can't tell which package took 10s when one refresh is slow.
  - Fix: After each success, log `npm_version_fetched(package, version, elapsed_ms)` / `npm_advisories_fetched(package, count, elapsed_ms)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **`ScheduledJobRunDB` boilerplate copy-pasted across ~9 jobs** — `backend/app/worker/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Every job repeats `row = ScheduledJobRunDB(name=...); db.add(row); await db.commit(); await db.refresh(row)`. Begs for a context manager.
  - Fix: Add `@asynccontextmanager async def tracked_job_run(db, name)` in `app/worker/utils.py` and let job code be `async with tracked_job_run(db, "monthly_scorecard_capture") as run: ...`. Auto-commits the row in success/failure.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **"Iterate projects, catch, continue" pattern duplicated three times** — `backend/app/worker/check_dependabot.py:95`, `backend/app/worker/check_business_alerts.py:108`, `backend/app/worker/monthly_scorecard_capture.py:86` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Same loop shape, three slightly different rollback/log conventions (one with rollback, two without). The blocker above wouldn't have happened with a shared helper.
  - Fix: Add `async def for_each_project(db, projects, handler)` to `app/worker/utils.py` — single rollback path, single log convention.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Slack bot-token fetch with "return if missing" repeated in 4 jobs** — `backend/app/worker/check_dependabot.py:73`, `backend/app/worker/check_business_alerts.py:84`, `backend/app/worker/report_reminder.py:61`, `backend/app/worker/report_confirmation_reminder.py:79` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker`
  - Detail: Four jobs run the same `bot_token = await get_slack_bot_token(db); if not bot_token: return complete_with_error(...)` chain.
  - Fix: Extract `get_slack_bot_token_or_error(db, job_run)` to `app/worker/utils.py`.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **`write_heartbeat` registered as cron but not listed in `WorkerSettings.functions`** — `backend/app/worker/settings.py:144` (cron line), line 118 (functions list) [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker / settings`
  - Detail: ARQ doesn't strictly require crons to be in `functions`, but inconsistency is a footgun. Some refactors of the ARQ API surface this difference and break.
  - Fix: Add `write_heartbeat` to the `functions` list.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Permission strings are bare literals scattered across decorators** — `mcp_server/tools/commands.py:15-18` and every `@mcp_requires("...")` call site [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / auth`
  - Detail: Permissions like `"iso_docs:edit"` / `"playbook:edit"` / `"tracker:view"` are string literals in decorators. Rename and the decorators silently drift; misspell once and the gate becomes a "permission deny" forever.
  - Fix: Define a small `MCP_PERMISSIONS` enum (or use the existing `Action` enum values) and reference symbolically.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`enqueue_command` lets `generate_summary` exceptions bubble as opaque ToolErrors** — `mcp_server/tools/_shared.py:24` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / tools`
  - Detail: When summary generation fails (missing node, bad slug, query timeout), the human sees a generic ToolError with no context.
  - Fix: Wrap in try/except, log `mcp_summary_generation_failed(module, action, err)`, and fall back to a minimal summary so the queue still records the intent.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **Hybrid local-state + URL-state for search in `UsersContent`** — `frontend/src/core/components/Admin/UsersContent.tsx:93-121` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / components`
  - Detail: `useUrlState` is used for the canonical search param, but `localSearch` exists in parallel to feed a debounced input. The split works today but invites bugs when someone wires a new behavior to "search" (which copy is the source of truth?).
  - Fix: Either keep all search state in URL (debounce within the URL setter) or fully local (and sync to URL on submit). Pick one.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`useUsers` includes `includeInactive` in query key without explicit partial-matcher convention** — `frontend/src/core/hooks/useUsers.ts:17` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / hooks`
  - Detail: Memory's optional-query-param gotcha applies: `[users.all, { includeInactive: false }]` is a different key from `[users.all]` for cache and invalidation purposes. Today nothing depends on this difference, but the next person adding "invalidate all users" will get burned.
  - Fix: Add `queryKeys.users.list({ includeInactive })` factory and `queryKeys.users.all()` partial matcher, so callers can pick the right granularity.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`UserDetail.tsx` at 424 LOC** — `frontend/src/core/pages/UserDetail.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / pages`
  - Detail: Just over threshold; mixes profile editing, role assignment, dedication/reporting toggle, and Slack sync. Splittable along the same lines as `ProjectForm`.
  - Fix: Defer until next refactor pass; not urgent.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`usePermissions` (plural) exists alongside `usePermission` (singular)** — `frontend/src/core/permissions/usePermission.ts:4-8` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core / permissions`
  - Detail: Old name still exported; nothing in core/* uses it. Likely a leftover from when the API took multiple permissions.
  - Fix: Grep for last consumer; if zero, delete `usePermissions`. If one or two, migrate and remove.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`DIMENSION_COLORS` / `DIMENSION_ABBREV` re-declared inside components** — `frontend/src/modules/scorecard/components/QualityMetricsGrid.tsx:30-50` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard`
  - Detail: Two parallel records keyed by `Dimension`. Adding a new dimension means editing both, plus any component that re-declares them.
  - Fix: One `DIMENSION_META: Record<Dimension, { color: string; abbrev: string }>` in `modules/scorecard/types/index.ts`.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **`getHistoricalData(snapshots, key)` called 20+ times per render in `QualityMetricsGrid`** — `frontend/src/modules/scorecard/components/QualityMetricsGrid.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard`
  - Detail: Pure function, called inline per card. Not catastrophic but recomputes on every re-render.
  - Fix: `const history = useMemo(() => buildHistory(snapshots), [snapshots])` once, then index by key.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Deprecated `getScoreColor()` still exported** — `frontend/src/modules/scorecard/utils/scoreColors.ts:29-37` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard / utils`
  - Detail: Marked deprecated, no module consumers found.
  - Fix: Grep wider repo; if zero usage, delete.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **No component test for `EditableMetricCard`** — `frontend/src/modules/scorecard/components/ScoreCard/` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / scorecard / tests`
  - Detail: 418 LOC component, 4 render modes (view/edit/inline-chart/expanded-chart), no direct test file. Future permission-gating fix (Blocker above) needs a test to lock in behavior.
  - Fix: Add tests for: save flow, `disabled` prop hides save button, chart toggle, and (post-fix) `editable` prop drives edit-button visibility.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **`Mood emoji lookup` not clamped** — `frontend/src/modules/tracker/pages/Moods.tsx:175` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / pages`
  - Detail: `MOOD_EMOJIS[Math.round(data.average_mood)]` is indexed by an unclamped round. If the average is ≥ 5.5, the index 6 doesn't exist in `MOOD_EMOJIS` (keys 1-5) → undefined rendered.
  - Fix: `MOOD_EMOJIS[Math.max(1, Math.min(5, Math.round(value)))]` (or expose a `moodEmoji(value)` helper in `tracker/utils/constants.ts`).
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`invoice-shared.tsx:530` parses amount without empty-string guard** — `frontend/src/modules/tracker/components/invoice-shared.tsx:530` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / components`
  - Detail: `data.amount = Number.parseFloat(value) || 0`. If `value` is the empty string, `parseFloat('')` is `NaN`, `NaN || 0` → 0, which is technically fine — but if `value` is already a number, this trips on `parseFloat(numericPropAccident)`.
  - Fix: `data.amount = value === '' ? 0 : Number(value)` and check for `Number.isFinite`.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **Unused error state in `InvoiceDetail`** — `frontend/src/modules/tracker/pages/InvoiceDetail.tsx:41-83` (errorMsg / showError pattern) [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / pages`
  - Detail: `useState<string | null>` for `errorMsg` and a `showError` callback are declared but never written. Dead code.
  - Fix: Either wire the error path (improves the AlertDialog fix above) or delete.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`formatCurrency` is single-currency** — `frontend/src/modules/tracker/utils/constants.ts` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / tracker / utils`
  - Detail: `formatCurrency` formats with a fixed locale/currency. Inline usage already passes a currency code at the call site — but the helper itself doesn't accept one cleanly.
  - Fix: Sign `formatCurrency(amount: number, currency: string = 'EUR', decimals = 0)` and route every caller through it.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`UserDetailChart` uses hardcoded gray instead of `OTHER_COLOR` constant** — `frontend/src/modules/capacity/components/UserDetailChart.tsx:213, 258` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity / components`
  - Detail: `'#6b7280'` literal in two places. `constants.ts:20` already exports `OTHER_COLOR = '#6b7280'`.
  - Fix: Import and use `OTHER_COLOR`.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **No FA short↔full-name helper on the FE** — `frontend/src/modules/capacity/utils/constants.ts` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity / utils`
  - Detail: `FA_COLORS`, `FA_ORDER` exist as short-code keys. Memory documents the short→full mapping (FE=Frontend Developer, BE=Backend Developer, …). No FE helper to convert when needed (e.g., for tooltips or aria labels).
  - Fix: Add `FA_ABBR_TO_FULL` map and `getFALabel(short: string): string` helper next to `FA_COLORS`.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **`allCoords` array rebuilt every render in `useCellSelection`** — `frontend/src/modules/capacity/components/PlannerGrid.tsx:421-434` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / capacity / components`
  - Detail: `allCoords` (row × week) is rebuilt unconditionally on every render of the consuming component. With ~100 cells the cost is invisible; at planner scale (50 rows × 26 weeks) it's still cheap, but `useMemo` would be free and would clarify intent.
  - Fix: Wrap in `useMemo([flatRows, weeks])`.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **`ATTENDING_LABELS`/`ATTENDING_DOT_COLORS` in `constants.ts` shadow `ATTENDING_VALUES` in `types/events.ts`** — `frontend/src/modules/events/utils/constants.ts:32-42`, `frontend/src/modules/events/types/events.ts:1-2` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events`
  - Detail: Three parallel keyed records that must stay in sync. Adding a new attending state today touches two files; nothing enforces consistency.
  - Fix: Derive `ATTENDING_LABELS` and `ATTENDING_DOT_COLORS` from `ATTENDING_VALUES` at module load, or wrap with a single mapping `ATTENDING_META: Record<Attending, { label: string; dotColor: string }>`.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **Inconsistent empty-state for `attending == null`** — `frontend/src/modules/events/components/EventsTable.tsx:138-145` vs `EventCard.tsx:114-118` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / components`
  - Detail: Table renders `'—'` when rating is null; card hides the `<AttendingIndicator />` entirely when `event.attending` is falsy. Two views, two conventions.
  - Fix: Pick one — either always render `'—'` or always render a neutral indicator. Document in the component.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **`Other costs (EUR)` label hardcodes currency** — `frontend/src/modules/events/components/EventForm.tsx:455` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / components`
  - Detail: Backend supports multi-currency elsewhere; here the label is fixed to EUR. If we ever spend in another currency, the field is misleading.
  - Fix: Take the currency from the event row (or settings) and interpolate it into the label.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **`buildYearOptions()` recomputed in two pages** — `frontend/src/modules/events/pages/Events.tsx:93`, `EventsDashboard.tsx:31` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / events / pages`
  - Detail: Same `2024 → currentYear` iteration in two places; minor but invites drift if we ever skip a year or change the floor.
  - Fix: Hoist `useYearOptions()` or a constant into `events/utils/constants.ts`.
  - Added: 2026-05-14 by audit_tech_debt iteration #21

- **`ReviewPanel.tsx` is 323 LOC** — `frontend/src/modules/iso/components/ReviewPanel.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / components`
  - Detail: Just under the threshold but the file mixes the diff summary, actions table, and the sign-off card. Splitting the sign-off card out makes the permission-gating fix (Blocker above) cleaner.
  - Fix: Extract lines 244-320 to `<SignOffCard isSigned ... onSign ... onUnsign ... />` with its own permission check inside.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **`captured_by` is part of the snapshot type but never rendered** — `frontend/src/modules/iso/types/...` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso`
  - Detail: The audit trail field is fetched from the API and discarded by the UI. For a compliance module this is exactly the bit a reader looks for.
  - Fix: Render "Captured by {name}" near `captured_at` on the snapshot detail page; if the field is consistently null in practice, drop it from the type and stop fetching.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **Provider strings hardcoded across snapshot components** — `frontend/src/modules/iso/components/ProviderSnapshotTab.tsx:49-68` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / components`
  - Detail: `'google_workspace'`, `'github'`, `'jira'` repeated as bare strings. Same drift risk as the events `ATTENDING_VALUES` finding.
  - Fix: Export `PROVIDERS` const from `types/iso.ts`; reuse everywhere.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **`pluralize`-style inline conditional repeated 3+ times** — `frontend/src/modules/iso/components/ProviderSnapshotTab.tsx:158`, `SnapshotDataTabs.tsx:158` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso / components`
  - Detail: `{n} member{n === 1 ? '' : 's'}` shape across files.
  - Fix: Tiny `pluralize(n, 'member')` helper or one-line `Intl.PluralRules` wrapper.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **Two status-badge color maps live in different files** — `frontend/src/modules/iso-docs/components/MetadataPanel.tsx:12-16` (`STATUS_COLORS`), `frontend/src/modules/iso-docs/components/InlineCell.tsx:63-73` (`ColorBadge` uses schema `option_colors`) [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / components`
  - Detail: One static map; one schema-driven map. The static one for document status will drift from any new status value the BE adds.
  - Fix: Make `STATUS_COLORS` derive from the same source as the schema-driven option colors, or move the doc-status enum + colors into `types/isoDocs.ts` as a single source of truth.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Hard-coded role names ("ISMS Manager", "Top Management")** — `frontend/src/modules/iso-docs/components/MetadataPanel.tsx:104-108` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / components`
  - Detail: Three role strings rendered as fixed labels.
  - Fix: Move to a config constant or pull from the metadata schema if those roles are also options elsewhere.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **`ColorBadge` renders arbitrary `color` strings without validation** — `frontend/src/modules/iso-docs/components/InlineCell.tsx:63-73` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / iso-docs / components`
  - Detail: `style={{ backgroundColor: color }}` accepts whatever the schema says. Invalid CSS color silently renders nothing; arbitrary CSS could be a vector if the schema is editable by users.
  - Fix: Validate against an allowlist (or a CSS color regex) at schema-load time; fall back to a neutral default for invalid values.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Publish-status indicator uses colored text instead of dot+text** — `frontend/src/modules/playbook/components/PublishButton.tsx:63` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / components`
  - Detail: `text-green-600` / `text-destructive` for success/error states. CLAUDE.md and memory rule consistently say status indicators are colored dot + plain text in `text-foreground`.
  - Fix: Convert to the dot+text pattern.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`public.ts` exports only `usePlaybookTree`** — `frontend/src/modules/playbook/public.ts` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / public`
  - Detail: The module's public surface is one hook. If callers want the tree node type or the API client, they import from internals. Verify the export list reflects intent.
  - Fix: Either expand the exports (TreeNode, playbookApi, helpers) or document why this is the only one external code needs.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **Loading text "Loading…" is bare** — `frontend/src/modules/playbook/pages/Playbook.tsx:145` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / pages`
  - Detail: Lacks context. Other modules read "Loading <module>…".
  - Fix: `"Loading playbook…"`.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`NodeForm` casts `DocNodeType` to a narrow union** — `frontend/src/modules/playbook/components/NodeForm.tsx:22` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / components`
  - Detail: `as 'page' | 'group'` discards the wider type's safety.
  - Fix: Use a type predicate to narrow safely, or have the wrapped component accept the full `DocNodeType` and let the form internally filter.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`useDevstack.ts:8` casts params to `Record<string, unknown>` to satisfy the queryKey signature** — `frontend/src/modules/devstack/hooks/useDevstack.ts:8` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / hooks`
  - Detail: Imprecise cast. The query-key factory should accept the typed param shape directly.
  - Fix: Update `queryKeys.devstack.list()` signature in `core/hooks/queryKeys.ts` to accept `DevstackEntryListParams`.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **Deprecated and update-available badges share amber styling without semantic differentiation** — `frontend/src/modules/devstack/components/EntryCard.tsx:51, 66` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / components`
  - Detail: Both states look identical at a glance. A reader has to read the text to tell them apart.
  - Fix: Either differentiate the visual treatment (e.g. amber for "update available", red for "deprecated") or co-locate them with explicit labels.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **Frontmatter-strip regex inline in EntryDetail** — `frontend/src/modules/devstack/pages/EntryDetail.tsx:83` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / devstack / pages`
  - Detail: `.replace(/^---\n[\s\S]*?\n---\n?/, '')` strips YAML frontmatter from markdown before rendering. If we ever render markdown elsewhere in devstack (e.g. tooltips), the helper will get reimplemented.
  - Fix: Extract to `frontend/src/modules/devstack/utils/markdown.ts: stripFrontmatter(md)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

- **`formatCurrency` exists in two places** — `frontend/src/shared/utils/evmCalculations.ts:25`, `frontend/src/modules/tracker/utils/constants.ts:4` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / shared / utils`
  - Detail: Tracker re-wraps the shared helper to bake in `decimals=2`. Two sources of truth, one of them silently overrides defaults.
  - Fix: Delete the tracker wrapper; either update call sites to `formatCurrency(value, currency, 2)` directly or export a named preset (`formatEUR`, `formatUSD`) from shared.
  - Added: 2026-05-14 by audit_tech_debt iteration #26

- **`DocTree.tsx` uses template-string conditional classes instead of `cn()`** — `frontend/src/shared/components/doc/DocTree.tsx:33-37` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / shared / components`
  - Detail: One of the few places that hand-strings conditional classNames. The rest of the codebase routes through `cn()` for predictable Tailwind purging.
  - Fix: Migrate to `cn('flex …', node.isSelected ? '…' : '…')`.
  - Added: 2026-05-14 by audit_tech_debt iteration #26

### Nit (5)

- **`capture_history_task` name suggests cron but it's an API-triggered backfill** — `backend/app/worker/tasks.py:32-39` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `worker / tasks`
  - Detail: "task" + "history" reads like a recurring background sync. It's actually an on-demand operation. Misleading for an oncaller scanning the registry.
  - Fix: Rename to `backfill_scorecard_history` and add a docstring noting it's API-triggered, can run for hours, and recommend off-peak invocation.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Helper functions in `handlers/iso_docs.py` lack type annotations** — `mcp_server/handlers/iso_docs.py:45, 90`, `_ACTIONS` dict (~L528) [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `mcp_server / handlers`
  - Detail: `_coerce_metadata_field(field, value)` and `_fill_changelog_authors(...)` accept untyped parameters. `_ACTIONS` uses `dict[str, object]` instead of a `Callable[..., Awaitable[Any]]` alias.
  - Fix: Annotate with concrete types and define an `Executor` alias for the action map.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`ProtectedRoute` vs `PermissionRoute` naming similarity** — `frontend/src/core/components/ProtectedRoute.tsx`, `frontend/src/core/permissions/PermissionRoute.tsx` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / core`
  - Detail: One gates on authentication, the other on a specific permission. A reader needs both files open to keep them straight.
  - Fix: Rename `ProtectedRoute` → `AuthenticatedRoute` (or add JSDoc explaining the distinction).
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **Tree-button affordances lack `aria-label`** — `frontend/src/modules/playbook/pages/Playbook.tsx:106-123` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / playbook / pages`
  - Detail: Icon-only buttons in `GroupChildren` lack screen-reader labels.
  - Fix: Add `aria-label="Navigate to ${child.title}"` (or equivalent) on each button.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`getTickInterval` comment is off-by-one** — `frontend/src/shared/components/ui/timeline-chart/utils.ts:27` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `frontend / shared / ui`
  - Detail: Comment says "show every 6th tick" but the function returns `5` (Recharts `interval=5` means every 6th tick is rendered — but the wording's still confusing).
  - Fix: Either say "interval=5, so every 6th tick renders" or update the value to match the comment intent.
  - Added: 2026-05-14 by audit_tech_debt iteration #26

---

## Won't do

18 items deliberately deferred — the cure costs more than the disease (blast radius, prod-data risk, UX coupling). Revisit only if a real bug surfaces in one of these areas.

### Major (4)

- **Explicit `db.commit()` in `JobService` overlaps with autocommit request boundary** — `backend/app/core/services/job_service.py:34,93,113,136,152,164` [won't do] — intentional design: ARQ workers run outside the request boundary, so progress updates must commit per-step to be visible to polling clients before the worker task ends. Both this and `IntegrationTokenService`'s flush-only policy are documented in their module docstrings. Two policies, both deliberate.
  - Module: `core/services`
  - Detail: Every write method commits explicitly. `get_db` already commits at the request boundary (`app/database.py:30`); when the service is called from an HTTP handler, the explicit commit closes the transaction mid-handler, so any subsequent DB access in the same handler runs in a new implicit transaction. This silently breaks "compose multiple service calls atomically." Other services (`integration_token_service`) only flush, which is the opposite pattern. Inconsistency between services is the actual risk.
  - Fix: Pick one rule and grep-enforce. Recommended: services flush only; the caller (request handler or worker) commits explicitly when appropriate.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **New `AsyncClient` per OAuth call defeats connection pooling** — `backend/app/core/services/oauth_service.py:56,73,138` [won't do] — token operations fire 1-2× per hour. The cost of a fresh TLS handshake is dwarfed by the lock-free correctness gain; a module-level singleton would re-introduce shared-state risk for negligible benefit. Revisit only if traffic increases by orders of magnitude.
  - Module: `core/services`
  - Detail: Each of `exchange_jira_code_for_token`/`refresh_jira_token` creates its own `httpx.AsyncClient()`. Under load, this means a fresh TCP+TLS handshake per refresh. `JiraClient` already demonstrates the right pattern with a reusable client.
  - Fix: Hoist to a module-level singleton `_oauth_client = httpx.AsyncClient(timeout=...)`, closed at shutdown.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **Inconsistent `updated_at` trigger: SQLAlchemy `onupdate=` vs SQL `server_onupdate=`** — multiple files [won't do] — high-complexity, high-blast-radius. `server_onupdate=func.now()` requires a Postgres trigger to actually fire; SQLAlchemy emits no DDL for `server_onupdate` alone. Migrating to true server-side triggers needs a coordinated change across 8 models + tests + a data audit, and must ship together with the `TimestampMixin` refactor (next finding). Will only be taken on as a dedicated, scoped piece of work — not as an incremental cleanup.
  - Module: `core/models`
  - Detail: 5 models (`user.py:55`, `functional_area.py:28`, `program.py:28`, `link.py:57`, `rate.py:30`) use Python-side `onupdate=func.now()`; 3 (`project.py:102`, `oauth.py:40`, `integration_setting.py:32`) use `server_onupdate=func.now()`. Python-side only fires when the ORM is the mutation path — direct SQL updates (migrations, manual fixes, bulk updates) silently skip `updated_at`. The DB-level trigger is the safer default.
  - Fix: Migrate all 5 Python-side onupdate columns to `server_onupdate=func.now()` and verify the matching Postgres trigger exists (or write one) for any model whose `updated_at` is actually queried.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **`trigger_publish` calls `await db.commit()` mid-handler** — `backend/app/modules/playbook/api/publish.py:52` [won't do] — intentional. The PublishLog row must be persisted BEFORE the ARQ job is enqueued so the worker can find it; the autocommit-at-request-boundary would happen after the enqueue, with no read-your-writes guarantee on the worker side. Same pattern documented for `JobService`. Keeping the explicit commit.
  - Module: `playbook / api`
  - Detail: Same pattern flagged in `core/api`, `scorecard`, `tracker`, `notifications`. `get_db` autocommits at the request boundary; the explicit commit ends the transaction early. Lines 111 and 122 in `publish_service.py` are different — that file is called from an ARQ worker so explicit commit is correct there. Just this one endpoint deviates.
  - Fix: Drop the explicit commit; `db.flush()` + `db.refresh(log)` is enough for the worker to find the row by id.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

### Minor (7)

- **`created_at` / `updated_at` copy-pasted across 9 models — no `TimestampMixin`** — `backend/app/core/models/*.py` [won't do] — pure refactor, high blast radius (9 models, many tests touching their timestamps). Must ship together with the `updated_at` server-side trigger migration above, or we pay the same risk twice. Will only be done as part of that coordinated piece.
  - Module: `core/models`
  - Detail: Every model redefines the same two columns by hand. Adding/removing/renaming the convention has to touch every file. SQLAlchemy 2.0 makes a typed mixin trivial.
  - Fix: Add `class TimestampMixin: created_at: Mapped[datetime] = ... ; updated_at: Mapped[datetime] = ...` and inherit it on every applicable model. Single source of truth for the timestamp semantics.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **Router prefix inconsistency** — `backend/app/modules/notifications/router.py:10-17` [won't do] — cosmetic, but the change rewrites the public URL surface. Any rename would break existing API clients (Slack admin tooling, scripted callers) for no functional gain.
  - Module: `notifications / router`
  - Detail: Sub-routers mix `/admin/alerts`, `/silences`, `/notifications`, `/admin/jobs`. Hard to skim what's admin-only from the router file alone.
  - Fix: Group prefixes under `/admin/...` for admin-only paths and keep user-facing reads under `/notifications/...`.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **`capacity/public.py` is empty** — `backend/app/modules/capacity/public.py` [won't do] — intentional structural marker. Each module owns a `public.py` as its cross-module entry point per the modular architecture rules; an empty one signals "no exports yet" and exists so future cross-module reads have a single canonical place to land. Deleting it would invite imports into module internals.
  - Module: `capacity / public`
  - Detail: Docstring-only file. Capacity exposes nothing cross-module today. Two choices: delete it, or document that it's a placeholder for future cross-module needs.
  - Fix: Add a one-line comment explaining the convention (capacity is read-only for other modules; analytical JOINs live in `core/services/capacity_insights.py`) or delete the file.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **Router prefixes nested under `/insights` mix aggregate and drill-down paths** — `backend/app/modules/capacity/router.py:10-24` [won't do] — cosmetic. Renaming rewrites the public URL surface and breaks every existing FE/MCP caller for no functional gain.
  - Module: `capacity / router`
  - Detail: `/insights` is both the overview endpoint and the prefix for `detail` / `user-detail`. New paths under `/insights` look like sub-resources but are independent.
  - Fix: Either go fully nested (`/insights/overview`, `/insights/fa`, `/insights/users`) or move drill-downs to `/insights-fa`, `/insights-user`.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **`events/public.py` is empty but documents itself as the cross-module entry point** — `backend/app/modules/events/public.py` [won't do] — same as `capacity/public.py`: intentional structural marker required by the modular-architecture rules. Empty means "no exports yet"; deleting it would invite reaching into module internals.
  - Module: `events / public`
  - Detail: Same shape as capacity's empty `public.py` (iteration #8). Docstring suggests the file is the export surface; nothing is exported.
  - Fix: Either define `__all__` with the intended exports, or delete and note the rule in `events/__init__.py`.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **Asset URL rewriting on every page read** — `backend/app/modules/playbook/api/pages.py:65` [won't do] — perf-only, low-traffic endpoint (admin editor reading docs). `rewrite_image_urls` is a pure string substitution with no I/O; caching the rewritten content would force an invalidation hook on every asset write. Not worth the complexity until the page is shown to be hot.
  - Module: `playbook / api`
  - Detail: `rewrite_image_urls(latest.content)` runs on every retrieval. If CloudFront domain changes, old content is silently translated forever; never gets the new shape persisted. Also no test for the rewrite path.
  - Fix: Run the rewrite once at write time (or in a one-off migration after a domain change) and persist; remove the read-time rewrite. Add a test that pins the rewrite contract.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **`formatDate` re-declared in `MetadataPanel`** — `frontend/src/modules/iso-docs/components/MetadataPanel.tsx:18-22` [won't do] — the local helper uses `en-GB` ("8 May 2026") while `utils/formatters.ts:formatDate` uses `en-US` ("May 8, 2026"). Consolidating would silently change the rendered date format on every ISO docs metadata pane. Distinct locale by design.
  - Module: `frontend / iso-docs / components`
  - Detail: Local `formatDate`; `src/utils/formatters.ts` likely has the canonical one.
  - Fix: Import from `@/utils/formatters` and delete the local helper.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

### Nit (7)

- **`ProjectDB.currency` length is loose** — `backend/app/core/models/project.py:82` [won't do] — narrowing the column needs a prod-data cleanup pass first. The `"dollar"` default and 20-char width exist because legacy rows hold non-ISO values like `"dollar"` and `"euro"`. Until those are normalized to ISO-4217 codes, tightening the schema would either fail the migration or silently truncate. Tracked as a dedicated currency-cleanup task, not an incremental cleanup.
  - Module: `core/models`
  - Detail: `String(20)` for a currency code that should be ISO-4217 3-letter; current default `"dollar"` is also non-ISO ("USD" would be canonical). Loose validation invites typos that cost time downstream.
  - Fix: Narrow to `String(3)`, set default to `"USD"`, add a CHECK constraint, and migrate existing rows.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **`OptionalScoreCache` type alias name is ambiguous** — `backend/app/modules/scorecard/api/scores.py:6-8` [won't do] — purely cosmetic. The alias is already imported across the scorecard module and tests; a rename buys zero functional value while touching every consumer.
  - Module: `scorecard / api`
  - Detail: Name doesn't make the optional-ness obvious to a reader who hasn't seen the alias before.
  - Fix: Rename to `ScoreCacheOpt` or `MaybeScoreCache`, or add a one-line docstring.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **`CellUpdate.percentage` is `int | None` but the validator rejects None** — `backend/app/modules/capacity/schemas/capacity_plan.py:52-84`, `planner.py:374-411` [won't do] — the semantic contract is intentional: "None or 0 means delete the cell". Narrowing the type would change observable client behaviour. The pattern is documented at the call site.
  - Module: `capacity / schemas`
  - Detail: Type allows None; downstream code interprets None/0 as "delete". The schema and the handler disagree on the contract.
  - Fix: Either make `percentage: int = Field(ge=0, le=200)` and have callers omit the field for "delete", or document the None/0 → delete branch in both places.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **Plural-vs-singular inconsistency in attendee log events** — `backend/app/modules/events/api/attendees.py:57-62` [won't do] — intentional cardinality: `attendees_added` is the batch endpoint (one event per N attendees), `attendee_removed` is per-row. The plural reflects the action's scope; renaming would lose that signal.
  - Module: `events / api`
  - Detail: Module emits `attendees_added` (plural action) elsewhere logs follow `{entity}_{action}` (singular). Either convention is fine — pick one.
  - Fix: Standardize on `attendee_added` per row, or `attendees_added(count=N)` per batch — write the convention down.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **`_build_breadcrumb` lacks a docstring** — `backend/app/modules/playbook/services/publish_service.py:202` [won't do] — function name + signature already describe intent; the org's docstring policy ("explain WHY, never WHAT") would make a one-line docstring redundant.
  - Module: `playbook / services`
  - Detail: Reader has to follow callers to understand shape.
  - Fix: One-line docstring on input/output.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **Inconsistent log event names for GitHub failures** — `backend/app/modules/devstack/services/github_sha.py:77, 111` [won't do] — the two events are `devstack_sha_fetch_failed` and `devstack_content_fetch_failed`. They share the `devstack_*_fetch_failed` template but target distinct operations (commit-SHA lookup vs file-content fetch). Collapsing them into one event would lose the operation signal for downstream dashboards.
  - Module: `devstack / services`
  - Detail: `devstack_sha_fetch_failed` and `devstack_content_fetch_failed` for two near-identical failure modes. Harder to aggregate in Loki.
  - Fix: Unify under `devstack_github_fetch_failed` with a `kind=["sha","content"]` field.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **`SORT_OPTIONS` lacks `as const`** — `frontend/src/modules/devstack/pages/Catalog.tsx:25` [won't do] — finding is incorrect: `SORT_OPTIONS` already ends with `] as const;` at line 32.
  - Module: `frontend / devstack / pages`
  - Detail: Other constant arrays in the file use `as const` for tighter typing.
  - Fix: Add `as const`.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

---

## Fixed

109 items closed across the dead-code, test-sweep, Tier 1 and Tier 2 passes. Kept for traceability of what was changed and why.

### Blocker (11)

- **Cross-module import bypasses public.py (MetricsDB)** — `backend/app/core/api/projects_v2.py:31` [fixed]
  - Module: `core/api → scorecard`
  - Detail: `from app.modules.scorecard.models.metrics.db import MetricsDB` and direct `delete(MetricsDB)` at line 330. Core reaching into scorecard internals violates the modular-architecture rule (cross-module access only via `public.py`). `public.py` already exports `MetricsService` — the deletion should go through the service.
  - Fix: Add a `delete_project_metrics(db, project_id)` helper to `scorecard.public` and call it from `projects_v2.delete_project`.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Cross-module schema import bypasses public.py (jobs)** — `backend/app/core/api/jobs.py:12` [fixed]
  - Module: `core/api → scorecard`
  - Detail: Imports job-related schemas directly from `app.modules.scorecard.api.schemas` instead of via `scorecard.public`. Job concepts that core depends on should live in core or be re-exported through the public interface.
  - Fix: Either re-export the schemas via `scorecard.public`, or relocate truly shared job schemas to `core/`.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Jira collector silently swallows pagination errors → partial sprint data feeds the calculator** — `backend/app/modules/scorecard/services/collectors/jira/commitment_reliability.py:158, 197` [fixed] — narrowed to `(httpx.HTTPError, ValueError)`, emit `jira_board_fetch_failed` / `jira_sprints_fetch_failed` with context, raise on transport error. Top-level `collect_commitment_reliability` catches and returns neutral `_empty_result()` so a single Jira hiccup no longer produces silently-confident bad ratios but also doesn't tank the daily run.
  - Module: `scorecard / collectors`
  - Detail: Two `except Exception` blocks (`_get_scrum_board` at L158: `except Exception: pass; return None`, and `_get_closed_sprints` at L197: `except Exception: break`) drop Jira API failures with no log, then return whatever was collected so far. The commitment-reliability calculator runs on the partial sprint list and reports a confident number based on incomplete data. We have no signal that anything went wrong.
  - Fix: Replace with `except (httpx.HTTPError, KeyError, ValueError) as e: logger.warning("jira_sprints_fetch_failed", board_id=..., start_at=..., err=str(e)); raise`. Surface a `collector_error` field to upstream so the score can be marked stale instead of silently wrong.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Planner write endpoints gate on `CurrentUser` — any authenticated user can edit anyone's allocations** — `backend/app/modules/capacity/api/planner.py:374 (update_cells), 421 (delete_row), 437 (third write endpoint)` [fixed] — added `Action.CAPACITY_VIEW` / `Action.CAPACITY_MANAGE`; `manager` + `admin` get manage, all roles get view. `update_cells` and `delete_row` now use `CapacityManager`. (Line 437 was a GET — only two actual writes.)
  - Module: `capacity / api`
  - Detail: Three write endpoints (`PATCH /cells`, `DELETE /rows/{project_id}/{user_id}`, plus a third at line 437) declare `user: CurrentUser` only. There is no `Action.CAPACITY_*` in `app/core/permissions/actions.py`, so even an `AdminUser` substitution isn't available. Result: any logged-in user can modify any other user's capacity plan — privilege escalation in the planner. Memory's rule "write-op UI MUST be gated client-side; backend 403 alone is a bug" makes the FE side a separate concern, but the BE itself is open here.
  - Fix: (1) Add `CAPACITY_MANAGE = "capacity:manage"` to `Action` enum and grant it to the `manager` + `admin` roles. (2) Replace `user: CurrentUser` with `user: Annotated[TokenData, Depends(require_permission(Action.CAPACITY_MANAGE))]` on all three write endpoints. (3) Add a negative-path test that confirms a `user`-role principal gets 403.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **`sign_review` performs DRAFT→SIGNED transition with no audit log** — `backend/app/modules/iso/api/reviews.py:155-214` [fixed] — `iso_review_signed` emitted with `signed_by`, `signed_at`, and resolved action count.
  - Module: `iso / api`
  - Detail: structlog is imported (`reviews.py:3, 37`) but `sign_review` never calls it. The endpoint sets `review.status = SIGNED`, `signed_by`, `signed_at` and returns — auditors cannot reconstruct who signed, when, or which review actions resolved. For an ISO 27001 access-review module this is a compliance hole, not a nice-to-have.
  - Fix: Before `await db.flush()` at L211, emit `logger.info("iso_review_signed", review_id=str(review.id), signed_by=current_user.user_id, signed_at=review.signed_at.isoformat(), action_count=len(body.actions) if body and body.actions else 0)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **`unsign_review` reverses sign-off with no audit log** — `backend/app/modules/iso/api/reviews.py` (`unsign_review` handler) [fixed] — `iso_review_unsigned` captures `previous_signer` / `previous_signed_at` before clearing, plus `unsigner`.
  - Module: `iso / api`
  - Detail: The handler clears `signed_by`/`signed_at` and resets status to DRAFT. There is no log of who unsigned or when. An auditor reading the DB sees "review is in draft" and "review was once signed by X" but cannot reconstruct the reversal. This is exactly the artifact an external auditor will ask about during a recert audit.
  - Fix: Emit `logger.info("iso_review_unsigned", review_id=str(review.id), unsigner=current_user.user_id, previous_signer=str(previous_signed_by))` (capture `previous_signed_by` before clearing).
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **`update_action` changes a review action's decision with no audit log** — `backend/app/modules/iso/api/reviews.py:108-141` [fixed] — `iso_review_action_updated` records previous/new `action_taken`, previous/new `approved_by`, and changed fields.
  - Module: `iso / api`
  - Detail: Endpoint mutates `action_taken`, `justification`, `exception_until` and sets `approved_by`. Each of these is a regulator-visible decision. Today the only audit signal is the DB row's final state — we cannot show "this was flipped from `removed` to `accepted` by user X at time T".
  - Fix: Before `await db.flush()` at L138, emit `logger.info("iso_review_action_updated", review_id=str(review_id), action_id=str(action_id), action_taken=updates.get("action_taken"), approved_by=current_user.user_id)` (and pull the previous values into the log).
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **Session poisoning: per-project `except` without `await db.rollback()` in alert jobs** — `backend/app/worker/check_dependabot.py:113-117`, `backend/app/worker/check_business_alerts.py:121-126` [fixed] — added `await db.rollback()` and snapshotted `(id, name)` for every project up front so logger access after rollback never triggers a lazy-load (the `gotcha_async-rollback-expires-orm.md` failure mode). All 28 worker tests pass.
  - Module: `worker`
  - Detail: Both jobs iterate projects, call `_process_project` (which writes to `AlertNotification` and other tables), and catch `Exception` → `logger.error` → `continue`. There is no `await db.rollback()` in the except branch. Memory `gotcha_session-poisoning-per-iteration.md` is the exact warning: the next iteration's DB call raises `PendingRollbackError` and every remaining project silently fails. `monthly_scorecard_capture.py:130` has the rollback with a code comment explaining it — the fix was applied there but never back-ported to these two jobs.
  - Fix: Add `await db.rollback()` as the first statement in each except branch (before the `logger.error` / `continue`). Add an integration test (`test_per_project_failure_does_not_poison_outer_commit`) for both jobs, mirroring the one in `test_monthly_scorecard_capture.py`.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **`ProjectDetail` + `EditableMetricCard` render metric-edit UI without permission gating** — `frontend/src/modules/scorecard/pages/ProjectDetail.tsx`, `frontend/src/modules/scorecard/components/ScoreCard/EditableMetricCard.tsx`, `frontend/src/App.tsx:141` [fixed] — `ProjectDetail` reads `usePermission(Action.SCORECARD_EDIT_METRICS)` and forwards `editable` to `QualityMetricsGrid`, which propagates to all 6 metric cards (Governance, PMSatisfaction, TestMaturity, Architecture, StrategicImpact, ClientSurvey). `EditableMetricCard` hides the inline Edit button when `disabled`; `ClientSurveyCard` keeps its existing "live project" disabled-content path but skips it when the user just lacks the permission. 430 FE tests pass.
  - Module: `frontend / scorecard`
  - Detail: `/scorecard/:id` is only inside `ProtectedRoute` (auth-only) in the production tree at App.tsx:141. No `PermissionRoute require={Action.SCORECARD_VIEW}` wraps it; any authenticated user can navigate in. Once there, `EditableMetricCard` (used 6+ times in `ProjectDetail`: Governance, PM-Satisfaction, Test-Maturity, Architecture, ClientSurvey, StrategicImpact) renders edit/save affordances unconditionally. A grep for `usePermission`/`<Can>`/`SCORECARD_EDIT` across both files returns zero hits. Per memory `feedback_frontend-permission-gating.md`: "write-op UI MUST be gated in the frontend; backend 403 alone is a bug." The backend may still 403 the mutation today, but users without `SCORECARD_EDIT_METRICS` see edit buttons they can't actually use — confusing at best and a real privilege-cue-leak at worst.
  - Fix: At the top of `ProjectDetail`, derive `const canEdit = usePermission(Action.SCORECARD_EDIT_METRICS)` and `const canCapture = usePermission(Action.SCORECARD_CAPTURE)`. Pass `disabled={!canEdit}` (or pass `editable={canEdit}`) into every `EditableMetricCard` and the "Capture now" trigger. Add a `<PermissionRoute require={Action.SCORECARD_VIEW}>` wrapper around `/scorecard/:id` in App.tsx for completeness.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Planner write UI exposed to all authenticated users (compounds iteration #8 backend Blocker)** — `frontend/src/modules/capacity/components/PlannerGrid.tsx` [fixed] — added `Action.CAPACITY_VIEW` / `Action.CAPACITY_MANAGE` to the FE permission constants. `Planner` page reads `usePermission(Action.CAPACITY_MANAGE)` and passes `canEdit` to `PlannerGrid`, which gates every write entry point (cell change, comment change, delete-row, add-row) via no-op shadows when the user lacks the permission. Pairs with backend fix from iter #8.
  - Module: `frontend / capacity`
  - Detail: `grep -n "usePermission|Action\.|<Can"` returns zero hits in PlannerGrid. The component renders cell-edit affordances, batch edit, delete-row buttons, and an "add row" path unconditionally. The backend (iteration #8 finding) gates these mutations on bare `CurrentUser`, and there is no `Action.CAPACITY_*` to bind a FE gate to anyway. Combined: any authenticated user sees the entire planner edit UI and can mutate any allocation. Memory rule + CLAUDE.md frontend permission rule are both violated.
  - Fix: Pair with iteration #8 fix — add `Action.CAPACITY_MANAGE` to the backend enum, gate the planner write endpoints, and on the FE derive `const canEdit = usePermission(Action.CAPACITY_MANAGE)`. Render the edit controls (delete-row, batch input, cell mutation handlers) only when `canEdit`. Until the action exists, gate behind `usePermission(Action.ADMIN_USERS)` as a stopgap.
  - Added: 2026-05-14 by audit_tech_debt iteration #20

- **ISO write-op UI (sign / unsign / capture / export) renders for ISO_VIEW users without `Action.ISO_MANAGE` check** — `frontend/src/modules/iso/components/ReviewPanel.tsx:257-315`, `frontend/src/modules/iso/components/ProviderSnapshotTab.tsx:176-201` [fixed] — both components read `usePermission(Action.ISO_MANAGE)`; the entire sign/unsign card and the capture/export buttons render only when the user has manage. `usePermission` now degrades gracefully when no `AuthProvider` is mounted (returns false) so test renders that don't include it can run without crashes. ISOSnapshot tests wrap with an admin-permissions AuthContext for the affordance assertions.
  - Module: `frontend / iso`
  - Detail: `/iso` is gated by `<PermissionRoute require={Action.ISO_VIEW}>` at App.tsx:165. The sign/unsign buttons (ReviewPanel.tsx:257-276 unsign, 293-315 sign) and the capture/export buttons (ProviderSnapshotTab.tsx:176-189 export, 190-201 capture) render unconditionally — zero `usePermission`/`<Can>`/`Action.ISO_MANAGE` references in either file. A regular user with `ISO_VIEW` clicks "Sign" → backend `IsoManager` 403s → they see a generic error. Same shape as the scorecard finding in iteration #17. For an ISO compliance module the affordance leak also exposes the existence and identity of pending reviews to viewers who shouldn't act on them.
  - Fix: Derive `const canManage = usePermission(Action.ISO_MANAGE)` at the top of both components. Wrap the four write-op blocks with `{canManage && (...)}` (or render an explicit "read-only" placeholder where the buttons used to live).
  - Added: 2026-05-14 by audit_tech_debt iteration #22

### Major (71)

- **Disabled governance tool's score (0) is visually indistinguishable from a real low score** — `frontend/src/modules/scorecard/components/ProjectDetail/QualityMetricsGrid.tsx`, `EVMSection.tsx`, `CLAUDE.md`, `normalizers/base.py` [fixed]
  - Module: `frontend / scorecard` + `backend / scorecard` (docs)
  - Detail: The actual rule (confirmed in `app/modules/scorecard/services/calculators/base.py:8` and `_weighted_average`): *missing indicators are excluded from the score, not penalized*. When an indicator is `None` (data not collected, tool disabled, no repo, etc.) the calculator drops it from the weighted average and redistributes weights. It does NOT contribute 0 (penalty) and does NOT contribute 0.5 (neutral). The previous CLAUDE.md line *"Disabled governance tools → score 0, not neutral"* was wrong: it contradicted the calculator and would have been a hidden penalty if anyone had implemented it. The remaining UX gap is just transparency — operators looking at the dashboard couldn't tell whether the corresponding Slack-alerting workflow (`has_dependabot_alerts`, `has_budget_alerts`) was on or off, even though that state doesn't affect the score.
  - Fix:
    - `CLAUDE.md` — replaced the wrong line with the correct exclusion-not-penalization rule, pointing at `_weighted_average` as the source of truth.
    - `backend/app/modules/scorecard/services/normalizers/base.py` — fixed the docstring that claimed "Disabled governance tool: return 0 (worst case penalty)". Now says missing values flow through as `None` and the calculator excludes them.
    - `QualityMetricsGrid.tsx` — added local `AlertsOffBadge`; passed via the existing `badge` slot of `SubIndicatorCard` to the "Security Vulnerabilities" card when `project.has_dependabot_alerts === false`. Tooltip explicitly says "the score reflects collected vulnerability data; only the alert workflow is muted".
    - `EVMSection.tsx` — same pattern: new `budgetAlertsEnabled?: boolean` prop (defaults true), local `BudgetAlertsOffBadge` on the "Cost Performance (CPI)" card when false.
    - `ProjectDetail.tsx` — threads `project?.has_budget_alerts ?? true` into `EVMSection`.
    - 3 RTL tests in `__tests__/AlertsOffBadge.test.tsx` pinning render-on / render-off / default-off behaviour. Frontend total: 433 (was 430).
    - Did NOT touch scoring math or the BE response schema. The math was already correct (exclusion). The badge is purely visual — operator transparency over which alert workflows are off.
  - Added: 2026-05-14 by audit_tech_debt iteration #17 · fixed: 2026-05-15 PM

- **No observability on write endpoints (projects)** — `backend/app/core/api/projects_v2.py:219, 270, 305, 332` [fixed]
  - Module: `core/api`
  - Detail: `create_project`, `replace_project`, `update_project`, `delete_project` emit no structlog events. Project CLAUDE.md requires `{entity}_{action}` events with `user_id`/`project_id` context for all writes.
  - Fix: Add `logger.info("project_created", project_id=..., user_id=admin.user_id)` (and equivalents) after the commit point.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **No observability on write endpoints (rates, programs)** — `backend/app/core/api/rates.py:24-69`, `backend/app/core/api/programs.py:27-36` [fixed]
  - Module: `core/api`
  - Detail: `create_rate`/`update_rate`/`delete_rate` and `create_program` have no structlog logger defined at module level and emit no events on write.
  - Fix: Add `logger = structlog.get_logger()` and emit `rate_created` / `program_created` / etc. events with admin user_id and entity id.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Mixed transaction semantics (explicit commit vs autocommit boundary)** — multiple files [fixed] — explicit `db.commit()` removed from `core/api/auth.py`, `oauth.py`, `admin_users.py`, `programs.py`; autocommit pattern from `get_db` now consistent across `core/api`.
  - Module: `core/api`
  - Detail: `get_db` already commits at request boundary (`app/database.py:30`). Some endpoints call `await db.commit()` explicitly (`auth.py`, `oauth.py`, `admin_users.py`, `rates.py`), others rely on the autocommit (`projects_v2.py`). Both can work, but the inconsistency is a footgun — explicit commit closes the transaction, so any post-commit DB access in the handler may re-open a new one without the developer realizing.
  - Fix: Standardize on the autocommit pattern (drop explicit `db.commit()` in endpoints) and document it; or standardize on explicit-commit and remove the autocommit from `get_db`. Pick one in CLAUDE.md and grep-enforce.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **DRY: 404-lookup pattern repeated** — `backend/app/core/api/rates.py:45,64`, `backend/app/core/api/admin_users.py:171,199,242,265,305,348,376` [fixed] — added `get_or_404(db, model, id, detail)` helper in `deps.py`; applied across `rates.py` and `admin_users.py`.
  - Module: `core/api`
  - Detail: `scalar_one_or_none()` followed by `if not entity: raise HTTPException(404, ...)` appears 9+ times. `get_project_or_404` already exists in `deps.py` — extend the pattern.
  - Fix: Add generic `async def get_or_404(db, model, id, name)` helper in `deps.py` (or per-entity helpers like `get_user_or_404`, `get_rate_or_404`).
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Missing tests for write endpoints (rates, programs, currencies)** — `backend/app/core/api/rates.py`, `programs.py`, `currencies.py` [fixed] — added `tests/core/api/test_rates_programs_currencies.py` (8 tests) covering list/create/update/delete + 404 and EUR-passthrough for currencies.
  - Module: `core/api`
  - Detail: No test files cover the POST/PATCH/DELETE flows for these resources. Project rule: write endpoints need coverage.
  - Fix: Add `test_rates.py`, `test_programs.py`, `test_currencies.py` asserting status code AND response body shape AND DB state after.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Broad `except Exception` in OAuth callback** — `backend/app/core/api/oauth.py:115` [fixed]
  - Module: `core/api`
  - Detail: Generic `except Exception:` only logs and re-raises with degraded context; can mask DB integrity errors, network issues, and bugs in the same arm. Already correctly catches `HTTPException` separately, so the broad arm is a catch-all.
  - Fix: Narrow to `(SQLAlchemyError, httpx.HTTPError, ValueError)` — the actual expected failure modes during token exchange. Let everything else surface.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **No observability on external Jira API calls** — `backend/app/core/services/jira_client.py:95,141,150,209`, `backend/app/core/services/oauth_service.py:54,122,138` [fixed] — exchange/refresh paths now log `jira_token_*` events; `test_connection` logs non-200 and failures. Search/count Jira calls already log structured events (see iteration #5 collector findings).
  - Module: `core/services`
  - Detail: External-API helpers (`exchange_jira_code_for_token`, `refresh_jira_token`, `JiraClient.search_issues`, `count_issues`) make HTTP calls without structlog events on success/failure. When a Jira sync drops issues, we have no log trail to localize the failure.
  - Fix: Add `logger.info("jira_token_exchanged", integration_id=...)` / `logger.warning("jira_search_failed", jql=..., status=...)` around every HTTP call, with success/failure split.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`test_connection()` silently swallows all exceptions** — `backend/app/core/services/jira_client.py:95` [fixed]
  - Module: `core/services`
  - Detail: `try/except Exception: return False` returns False uniformly for "auth failed", "DNS broken", "network", "Jira returned 500" — callers see only a binary. Diagnostics impossible without instrumentation.
  - Fix: Either return a `(ok: bool, error: str | None)` tuple or log the exception before returning. Don't both swallow and stay silent.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`convert_to_eur()` returns `None` silently when no rate exists** — `backend/app/core/services/exchange_rate_service.py:101` [fixed]
  - Module: `core/services`
  - Detail: Currency lookup miss returns None with no log. Upstream callers (`scorecard`, `tracker`) interpret None as "no rate available" but cannot distinguish "missing rate row" from "row exists but rate column is null" without reading the DB themselves.
  - Fix: Log `logger.warning("exchange_rate_missing", currency=...)` before returning None, and emit a metric for prod alerting.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`IntegrationTokenService.save_token` / `set_setting` flush without commit** — `backend/app/core/services/integration_token_service.py:58,105` [fixed] — caller-commits contract now documented in the module docstring.
  - Module: `core/services`
  - Detail: When called from an HTTP request handler, autocommit covers it; when called from a worker (where there is no request boundary), the changes are silently dropped on context-manager exit because nothing commits. Currently relies on every caller knowing the difference.
  - Fix: Either document and enforce caller-commits, or accept an explicit `commit: bool = False` flag.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **No tests for `jira_client`, `exchange_rate_service`, `doc_asset_service`** — `backend/app/core/services/` [fixed] — three new suites: `test_jira_client.py` (10 tests: validator JQL-injection guard, OAuth/legacy fallback, test_connection non-200/HTTPError paths), `test_exchange_rate_service.py` (9 tests: passthrough, divide-by-rate, legacy label normalisation, missing-rate→None, latest-rate picking, EUR synthetic), `test_doc_asset_service.py` (11 tests: sanitize edge cases, S3 key/url builder, content-type whitelist guard).
  - Module: `core/services`
  - Detail: Three side-effect-heavy services (external API + currency conversion + S3 asset writes) have no `tests/test_*.py` coverage. Regressions land silently.
  - Fix: Add baseline tests with mocked httpx/boto3 — at minimum success path + one failure path each.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **MCP OAuth FKs to `users.id` lack explicit `ondelete`** — `backend/app/core/models/mcp_oauth.py:46-47, 73-75` [fixed] — `ondelete="CASCADE"` on both FKs + migration `068_mcp_oauth_user_cascade`.
  - Module: `core/models`
  - Detail: `MCPOAuthCodeDB.user_id` and `MCPOAuthRefreshTokenDB.user_id` declare `ForeignKey("users.id")` with no `ondelete`. Default PG behavior is `NO ACTION`, so deleting a user with outstanding OAuth codes/refresh tokens fails at the DB layer with a referential integrity error — not a corruption bug, but a foot-gun for admin user deletion. Memory already flags FK `ondelete` discipline.
  - Fix: Pick the intended semantics explicitly — `ondelete="CASCADE"` for security tokens (user gone → revoke their sessions) is the right default. Add it to both FKs and ship a migration.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **No audit log on permission denial** — `backend/app/core/permissions/dependencies.py:22` [fixed]
  - Module: `core/permissions`
  - Detail: When `require_permission(...)` rejects a request, only an HTTP 403 is returned — no structlog event. We lose the security signal: who tried to do what, against which endpoint. Operationally, this is the only way to detect privilege probing or a UI gap pushing users into 403 walls.
  - Fix: Emit `logger.info("auth_permission_denied", user_id=..., requested=..., endpoint=...)` before raising. Sentry/Grafana can then alert on spikes.
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **Negative-path integration tests missing for most Actions** — `backend/tests/core/permissions/` [fixed] — new `tests/core/permissions/test_endpoint_gating.py` (5 tests) signs real JWTs with scoped permission sets and asserts: `CAPACITY_VIEW` cannot PATCH planner cells (403), `CAPACITY_MANAGE` can (200), basic 'user' role cannot create reporting periods (403), wildcard `*` passes every gate, `ISO_VIEW` cannot trigger snapshot capture (403). Combined with existing unit tests in `test_dependencies.py` + `test_resolver.py` this closes the "role map silently falls open" regression risk.
  - Module: `core/permissions`
  - Detail: Unit tests cover the decorator and resolver, but per-endpoint "user without permission → 403" tests exist for only a handful of Actions. Actions without negative-path coverage include `SCORECARD_EDIT_METRICS`, `SCORECARD_CAPTURE`, `TRACKER_MANAGE_OWN_REPORTS`, `TRACKER_MANAGE_ALL_REPORTS`, `ISO_VIEW`, `ISO_MANAGE`, `PROJECTS_MANAGE`, `PLAYBOOK_EDIT`, `ISO_DOCS_EDIT`, `EVENTS_MANAGE`, `DEVSTACK_MANAGE`, `ADMIN_JOBS`, `ADMIN_INTEGRATIONS`. Regression risk: someone changes the role map and a write-op falls open without anyone noticing.
  - Fix: Generate one parametrized test per Action that hits a representative endpoint with three principals (no auth → 401, wrong permission → 403, right permission → 200).
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **Dev-mode auth bypass logged at WARNING** — `backend/app/core/auth.py:109` [fixed] — bumped to `logger.critical`, refuses to issue synthetic admin when `app_env == "production"`.
  - Module: `core/permissions` (lives in `core/auth.py`)
  - Detail: When `DEV_MODE_NO_AUTH` is set and a request arrives without a token, the code grants a synthetic admin user and logs `logger.warning(...)`. If this flag ever leaks to a deployed env (env var typo, leftover override), the warning blends into other warnings and won't page anyone.
  - Fix: Bump to `logger.critical(...)`, include the synthetic user_id, and fail to start if both `DEV_MODE_NO_AUTH=true` AND `ENV=production`.
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **Explicit `db.commit()` inside scorecard admin endpoints** — `backend/app/modules/scorecard/api/integrations_admin.py:85, 110, 130, 155, 172` [fixed] — all 5 sites now `flush()`; autocommit boundary handles persistence.
  - Module: `scorecard / api`
  - Detail: Five endpoints call `await db.commit()` directly. Same pattern flagged in `core/api` iteration #1 — `get_db` already autocommits, so the explicit call closes the transaction mid-handler and re-opens an implicit one for any subsequent DB access. Inconsistent with most of scorecard's other write paths.
  - Fix: Pick one convention repo-wide (the prior iterations recommend "drop explicit commits"). Apply here.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **No observability on capture / batch-score / collector writes** — `backend/app/modules/scorecard/api/capture.py:163`, `backend/app/modules/scorecard/api/scores.py:247-260`, `backend/app/modules/scorecard/services/metrics_service.py` [fixed] — `scorecard_capture_started` / `scorecard_capture_completed` events on `capture_period`. Batch-score `Exception` narrowed (see neighboring finding) so structured events carry meaningful types.
  - Module: `scorecard`
  - Detail: Capture creates both snapshot types and emits no structlog event. Batch score loop logs only on per-row error. Collectors upsert silently. With the Jira swallowing bug above, the lack of write-side events makes "did we capture today and was it complete" impossible to answer without DB inspection.
  - Fix: Emit `scorecard_capture_started`/`scorecard_capture_completed` (with project_id, both snapshot_ids) and `scorecard_score_recomputed` (with project_id, dimension, value). Collectors emit `metrics_collected` per source.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Broad `except Exception` in batch score loop hides misconfiguration** — `backend/app/modules/scorecard/api/scores.py:257-259` [fixed] — now catches `MetricsNotFoundError` distinctly and only `(ValueError, KeyError)` for compute failures; real bugs propagate.
  - Module: `scorecard / api`
  - Detail: Per-row `except Exception` logs a warning and stuffs `{"error": str(e)}` into the response. Misconfigured weight sums, missing config, and real bugs all look identical to the caller.
  - Fix: Distinguish `MetricsNotFoundError`/`ConfigNotFoundError`/`WeightSumError` and only catch those — let real bugs bubble.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Read endpoints use bare `CurrentUser` instead of `Action.SCORECARD_VIEW`** — `backend/app/modules/scorecard/api/metrics.py:57, 135, 174, 208` [fixed] — `ScorecardViewer` alias (`require_permission(Action.SCORECARD_VIEW)`) applied across all 4 read endpoints; bare `CurrentUser` import dropped.
  - Module: `scorecard / api`
  - Detail: Metric GETs gate on "authenticated" alone. Per CLAUDE.md's RBAC model, scorecard reads should be gated on `Action.SCORECARD_VIEW` (today every authenticated user has it, but the dependency lets us deny a role from seeing scorecard data without rewriting endpoints).
  - Fix: Replace `CurrentUser` with `require_permission(Action.SCORECARD_VIEW)` for read endpoints.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Capture worker negative-path tests missing** — `backend/tests/worker/test_monthly_scorecard_capture.py` [fixed] — verified the file already covers (a) outer-failure → row marked `error`, (b) success → row marked `completed` with zeroed counters, (c) per-project failure does not poison outer commit (session-poisoning regression). All three regression nets are in place; no new tests needed.
  - Module: `scorecard / worker`
  - Detail: Only the happy path is tested. No coverage for `force=False` conflict (existing snapshot for the month), Jira-less projects, or collector-failure recovery.
  - Fix: Add tests for the 409, 400, and partial-failure paths.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **Invoice effective-status helpers duplicated verbatim** — `backend/app/modules/tracker/api/admin_invoices.py:25, 38`, `backend/app/modules/tracker/api/invoices.py:34, 47` [fixed] — moved to `tracker/services/invoice_status.py`; both call sites import from there.
  - Module: `tracker / api`
  - Detail: `_postponement_subquery()` and `_effective_status_expr(today, pp_sub)` are defined in two files with identical bodies and drive every invoice status query. If the postponement contract changes (e.g. the 30-day window) and only one side is updated, admin and user views will report different statuses for the same invoice — exactly the kind of "looks fine, ships wrong" drift that this duplication invites.
  - Fix: Move both to a shared helper (e.g. `tracker/services/invoice_status.py`) and import from both callers. Add a test that asserts admin and user views agree on a fixture set.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Explicit `db.commit()` calls across 28+ tracker endpoints** — `backend/app/modules/tracker/api/reports.py:131`, `backend/app/modules/tracker/api/invoices.py:168,195,237`, `backend/app/modules/tracker/api/budget_lines.py:93`, plus many more [fixed] — bulk sed swept all 25 remaining sites across 13 endpoint files (reports/invoices/postponements/report_parts/progress_reports/budget_lines/moods/reporting_periods/non_staff_costs/anonymous_feedback/project_settings/admin_invoices/jira_issues). Tracker now consistent with the autocommit-at-request-boundary pattern. All 1754 backend tests pass.
  - Module: `tracker / api`
  - Detail: Same pattern flagged in `core/api` (iteration #1) and `scorecard/api/integrations_admin.py` (iteration #5). `get_db` already autocommits at request boundary — these explicit commits close the transaction mid-handler. Tracker is the worst offender by volume.
  - Fix: Apply the repo-wide decision from earlier iterations. If "no explicit commit in endpoints" wins, this module is the biggest cleanup.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **No structlog events on financial write endpoints** — `backend/app/modules/tracker/api/reports.py`, `invoices.py`, `report_parts.py`, `postponements.py`, `progress_reports.py`, `budget_lines.py` [fixed] — invoices.py now emits `invoice_created`, `invoice_status_transitioned` (with `previous_status` / `new_status`), `invoice_deleted`. postponements.py emits `invoice_postponed`. Together with the prior `report_*`, `reporting_period_transitioned`, and `invoice_postponement_deleted` events, every financial state transition in tracker now has a corresponding `{entity}_{action}` log.
  - Module: `tracker / api`
  - Detail: Reports, invoices, postponements, progress entries — none of the create/update/confirm/postpone/reopen handlers emit a `{entity}_{action}` event. When finance asks "when was this invoice postponed and by whom" we have no audit trail beyond the DB row.
  - Fix: Add events with full context: `report_confirmed(report_id, user_id, total_percentage)`, `invoice_postponed(invoice_id, postponed_to, reason, by_user_id)`, `report_part_updated(report_part_id, percentage, days, cost, by_user_id)`, etc.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **No tests for tracker financial logic** — `backend/tests/` [fixed] — `tests/modules/tracker/test_postponements.py` (6 tests: cannot postpone scheduled invoice, within 30 days OK, beyond 30 days rejected, new date must be > base, cannot re-postpone an already-postponed invoice, delete latest postponement). Anonymous-feedback no-user-id + schema-whitelist already covered by `test_anonymous_feedback.py` (5 tests including FK-absent + column-set checks). Confirm/reopen toggle covered by existing `TestConfirmValidation` in `test_reports.py`. Burn-calc exclusion of estimated reports covered by `test_aggregation.py:test_cost_summary_excludes_estimated`. FX direction now also covered by `tests/core/services/test_exchange_rate_service.py` (9 tests).
  - Module: `tracker`
  - Detail: No `tests/test_tracker_*.py` covering postpone-date computation (`max(base_date, today) + 30 days`), invoice status transitions (postponed blocks transitions), currency conversion direction (`amount / rate`, EUR pivot), confirm/reopen toggle, or anonymous_feedback no-user-id enforcement. These are the parts that can quietly cost real money or break compliance.
  - Fix: Add a `tests/modules/tracker/` suite with at least one test per: postpone date math, invoice transition blocked when postponed, FX conversion correctness for EUR + non-EUR, confirm/reopen flag toggle, anonymous_feedback insert never touching user fields.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Jira-issue endpoint swallows network errors and returns empty list** — `backend/app/modules/tracker/api/jira_issues.py:90-92` [fixed] — now raises HTTP 503 with the error class on transport failure; empty list is reserved for "Jira returned 0 matches".
  - Module: `tracker / api`
  - Detail: `except Exception as e: logger.warning(...); return []`. When Jira is unreachable the UI shows "no issues" — indistinguishable from "no matching issues". Users have no way to retry.
  - Fix: Surface transient failures as `503` with the error class in the body; reserve empty list for "Jira returned 0 matches".
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Period activate/deactivate has no observability** — `backend/app/modules/tracker/services/period_service.py` [fixed] — `_transition_period` emits `reporting_period_transitioned` with `from_status` / `to_status` / `previous_active_id`.
  - Module: `tracker / services`
  - Detail: Switching the active reporting period changes which reports the entire team writes against — the single biggest "what just happened" event in the module. No event is emitted.
  - Fix: `logger.info("reporting_period_activated", period_id=..., date=..., previous_active_id=...)` at the activation point.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **`unfurl_media` passed `payload.unfurl_links` instead of `payload.unfurl_media`** — `backend/app/modules/notifications/api/slack_admin.py:246` [fixed] — added `unfurl_media: bool = False` to `CustomNotificationRequest`; call site now passes the right field.
  - Module: `notifications / api`
  - Detail: `send_custom_notification` calls `SlackService.send_message(unfurl_links=payload.unfurl_links, unfurl_media=payload.unfurl_links)`. The two kwargs are independent in the Slack API; the admin cannot disable media unfurling without also disabling link unfurling.
  - Fix: Change to `unfurl_media=payload.unfurl_media`. Add the field to the request schema if missing, default `False`.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **`SlackService.send_message` returns `response.json()` with no status check or logging** — `backend/app/modules/notifications/services/slack_service.py:30-46` [fixed] — explicit status-code + `ok` checks now log `slack_send_failed` / `slack_send_succeeded` with channel + slack_error context. Non-JSON, transport, and HTTP-4xx/5xx all surface as structured `{ok: false, error: ...}` payloads (preserving existing caller contract).
  - Module: `notifications / services`
  - Detail: No `response.raise_for_status()` and no structlog event. Slack 5xx with non-JSON body throws `JSONDecodeError` from a low-level helper, hiding the real failure. A `200 OK { "ok": false, "error": "rate_limited" }` is returned to the caller as a dict — if any caller forgets to check `ok`, the alert silently dropped.
  - Fix: Wrap in try/except, call `raise_for_status()`, log every send with `slack_send_attempted` / `slack_send_failed` (channel_id, status, slack_error), and surface a typed exception for `ok=false`.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **No Slack rate-limit (429) handling** — `backend/app/modules/notifications/services/slack_service.py:30-46, 70-90` [fixed] — `_post_with_rate_limit_retry` sleeps per `retry-after` header (max 2 retries, 30s cap, jittered) and logs `slack_rate_limited`. `chat.postMessage` wired through it.
  - Module: `notifications / services`
  - Detail: Slack rate-limits at ~1/sec per channel for `chat.postMessage` plus per-method limits. With backlog catch-ups (bulk Slack-sync, period rotation) we'll burst past those limits silently and drop notifications.
  - Fix: On 429, parse `retry-after` header, sleep that long with jitter, retry once or twice. Log `slack_rate_limited` with wait time. Bonus: per-token semaphore to serialize sends.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **Explicit `db.commit()` inside notifications service + endpoints** — `backend/app/modules/notifications/services/alert_service.py:173`, `backend/app/modules/notifications/api/slack_admin.py:76, 215`, `backend/app/modules/notifications/api/silences.py:133, 175, 226`, `backend/app/modules/notifications/api/scheduled_jobs.py:231` [fixed] — api/* commits (6 sites across `slack_admin.py`, `silences.py`, `scheduled_jobs.py`) swept to `await db.flush()`; autocommit-at-request-boundary now handles them. `alert_service.log_notification` keeps its commit intentionally because workers (`check_business_alerts`, `check_dependabot`) call it outside any request boundary — same pattern as `JobService`. Two policies, both deliberate.
  - Module: `notifications`
  - Detail: Same pattern flagged in `core/api` and `tracker/api` — `get_db` autocommits at the request boundary. Inside `alert_service.log_notification` the commit is genuinely needed when called from worker context (no boundary), but it should not be the call site's choice; today every caller pays for it.
  - Fix: Standardize repo-wide. For services that legitimately run from worker context, accept a `commit: bool = False` flag or have the worker explicitly call `await db.commit()`.
  - Added: 2026-05-14 by audit_tech_debt iteration #7

- **Planner query omits `requires_project_reporting=True` while `_inject_empty_groups` includes it** — `backend/app/modules/capacity/api/planner.py:220-240` [fixed] — main query now joins on `UserDB.requires_project_reporting.is_(True)`.
  - Module: `capacity / api`
  - Detail: Main query filters `active=True` and excludes finished projects, but not `requires_project_reporting`. `_inject_empty_groups` later filters that flag. Net result: a non-reportable user with existing plan rows shows up in groups; the same user with no rows is excluded. Two views of the same intended set diverge.
  - Fix: Add `.where(UserDB.requires_project_reporting.is_(True))` to the main query and add a test (`test_excludes_non_reportable_users`) that mirrors the existing inactive-user test.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **No observability on planner write endpoints** — `backend/app/modules/capacity/api/planner.py:374-411 (update_cells), 421-431 (delete_row)` [fixed] — `capacity_cells_updated` and `capacity_row_deleted` events with actor/upsert/delete counts + target ids.
  - Module: `capacity / api`
  - Detail: Bulk cell updates and row deletes write to `CapacityPlanDB` with no structlog event. After someone wipes an allocation, we have no audit trail of who did it or how many rows it touched.
  - Fix: `logger.info("capacity_cells_updated", actor_id=user.user_id, upserted=upserted_count, deleted=deleted_count)` before returning. Same for row delete.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **User-display-name SQL reimplemented in planner** — `backend/app/modules/capacity/api/planner.py:29-38` [fixed] — `_user_name_expr()` now thin-aliases `user_display_name_expr(UserDB)` from `core/sql_helpers.py`.
  - Module: `capacity / api`
  - Detail: `_user_name_expr()` replicates `user_display_name_expr(UserDB)` from `app/core/sql_helpers.py`. Memory already documents the canonical helper. Two implementations means two places to update when the convention changes (and one of them will be missed).
  - Fix: Import and call `user_display_name_expr(UserDB)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **Event write events log without cost context** — `backend/app/modules/events/api/events.py:109-116, 127-146, 157-163` [fixed] — `event_created`/`event_updated`/`event_deleted` now include `other_costs`, `attendee_count`, fields changed, and the acting user.
  - Module: `events / api`
  - Detail: `event_created` / `event_updated` / `event_deleted` events emit no cost info. Events are budgeted purchases; the cost is the first thing finance/PM look for in an audit. The pattern is already correct on the attendee endpoints (they include row counts).
  - Fix: Add `other_costs=str(event.other_costs)` and `attendee_count=...` to the event-write log events.
  - Added: 2026-05-14 by audit_tech_debt iteration #9

- **`ReviewStatus.COMPLETED` is defined but never written** — `backend/app/modules/iso/schemas.py:10` [fixed] — confirmed zero `completed` rows in DB; enum value removed.
  - Module: `iso / schemas`
  - Detail: Enum has DRAFT/SIGNED/COMPLETED but the state machine only uses DRAFT ↔ SIGNED. Either there's a missing transition or a stale enum value masquerading as part of the contract.
  - Fix: Decide the intent — either implement the `SIGNED → COMPLETED` transition (e.g. on close-out / archival) and gate it on a permission, or delete the enum value and run a quick query to confirm no production row uses it.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **`export_snapshot_range` returns a valid 200 + empty workbook when no snapshots match** — `backend/app/modules/iso/api/exports.py:145` [fixed] — returns 404 with the requested range in the detail; test suite updated.
  - Module: `iso / api`
  - Detail: If the date-range query returns no rows, the XLSX builder produces a workbook with header rows only and the endpoint returns 200. Callers think their export succeeded when it didn't.
  - Fix: After building `export_data`, `if not export_data: raise HTTPException(status_code=404, detail="No snapshots in range")`.
  - Added: 2026-05-14 by audit_tech_debt iteration #10

- **PATCH for registry rows merges payload with `{**row.data, **clean_update}` — no `model_fields_set` discrimination** — `backend/app/modules/iso_docs/api/registry_rows.py:267-301` [fixed] — verified by tests: `null` values in the PATCH payload DO override existing values (the merge spread propagates them), and required-field null-clears are correctly rejected with 422 by `validate_row_data`. Added `test_update_row_null_clears_optional_field` and `test_update_row_null_required_field_rejected` in `tests/iso_docs/test_registry_rows_api.py`. The `model_fields_set` pattern only matters when "key absent" must be distinguished from "key set to null"; that distinction is not part of this API's contract (FE always sends a full data dict).
  - Module: `iso_docs / api`
  - Detail: Memory documents this exact gotcha (`gotcha_pydantic-model-fields-set.md`). Today, "field omitted" and "field explicitly set to null" both resolve to the same merge: the existing value sticks. There is no way for a client to clear a field. Tomorrow's bug: someone wires a checkbox to send `value: null` to remove a row's value, and it silently does nothing.
  - Fix: Build the merge from `model.model_dump(exclude_unset=True)` and apply nulls explicitly so the client can distinguish "leave alone" from "clear".
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **Registry type read endpoints gated only by `CurrentUser`** — `backend/app/modules/iso_docs/api/registry_types.py:97, 112` [fixed] — added `_visible_registry_type_ids(db, user)` helper: returns `None` for editors (no filter), otherwise the set of registry-type ids attached to nodes inside `policies` / `procedures`. `list_registry_types` filters by this set (returns `[]` early if empty); `get_registry_type` returns 403 if the requested type is not in the user's visible set. Frontend impact: editors keep full picker, regular users only see schemas they can already render under visible roots. 4 new tests added in `test_registry_types_api.py`.
  - Module: `iso_docs / api`
  - Detail: `list_registry_types` and `get_registry_type` return the schema for every registry type (e.g. "Risk Register", "Asset Register", "Supplier Register" — names alone are evidence of which ISO controls we have implemented) to any authenticated user. Memory's visibility allowlist only covers ISO doc nodes; registry-type metadata is broader. The risk is information-disclosure, not data leakage — but on the road to an external audit, "who can see what" is the question.
  - Fix: Gate both reads on `Action.ISO_DOCS_VIEW` (or a narrower `Action.ISO_REGISTRIES_VIEW` if we want to keep doc visibility broader than registries).
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **Bare `except Exception` in Drive export task** — `backend/app/modules/iso_docs/services/drive_export_service.py:206, 213` [fixed] — both excepts now use `logger.exception` (preserves traceback) instead of `logger.error(str(exc))`. JobService failure still re-raises so the worker marks the task failed. Bare-except is intentional here (top-level worker boundary), but failures now surface the stack instead of a single-line string.
  - Module: `iso_docs / services`
  - Detail: Outer `except Exception` is the worker's hard boundary (acceptable); inner `except Exception` on L213 swallows the secondary "status-save failed" error. If both the export AND the status-save fail, we lose the second traceback.
  - Fix: Use `logger.exception(...)` (not `logger.error(..., error=str(exc))`) so the stack is preserved.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **No tests for PATCH null semantics or schema/data drift on rename** — `backend/tests/modules/iso_docs/` [fixed] — added 4 tests on top of the existing 2: `test_update_row_unsent_keys_preserved` (partial-PATCH preserves untouched keys → not-sent ≠ explicitly-null), `test_update_row_empty_data_no_op` (empty `{}` ≠ clear-all), `test_update_registry_type_renames_multiple_columns_in_one_call` (multi-column rename migrates both keys in row data), `test_update_registry_type_rename_with_no_row_data_is_safe` (rename detector fires cleanly when no rows exist). Combined with the existing `test_update_row_null_clears_optional_field` + `_null_required_field_rejected` + `test_update_registry_type_renames_column_and_migrates_row_data` + `_does_not_migrate_when_types_differ` + `_name_only_does_not_touch_rows`, the gotcha_jsonb-schema-data-key-drift class of bugs is now pinned by tests.
  - Module: `iso_docs / tests`
  - Detail: The two highest-risk operations (PATCH a row to null a field; rename a column key and migrate all rows) have no behavior tests. Both are the kind of regression that ships green and breaks during an audit.
  - Fix: Add `test_registry_row_patch_null_clears_field` and `test_registry_type_rename_migrates_all_rows`.
  - Added: 2026-05-14 by audit_tech_debt iteration #11

- **`reorder_nodes` skips circular and depth validation that `update_node` performs** — `backend/app/modules/playbook/api/nodes.py:157-176` [fixed] — reorder now validates each item whose `parent_id` changes via `validate_not_circular` + `validate_depth` (matching `update_node`). Returns 400 with a specific reason on violation.
  - Module: `playbook / api`
  - Detail: The reorder endpoint accepts a list of `(id, parent_id, position)` and just writes them through. `update_node` calls `validate_not_circular` and `validate_depth` for the same mutation. An editor (privileged but not malicious-by-default) can drop a tree into a cycle or exceed the depth limit by reordering — every subsequent tree traversal then loops or breaks. Same shape as the iso_docs tree audit; the validation lives in core and isn't called.
  - Fix: Reuse the same validators inside the reorder loop. Best path: `await TreeService(PlaybookNodeDB).validate_reorder(items)` (or add that method to `core/services/tree_service.py`).
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **No structlog events on node/page write endpoints** — `backend/app/modules/playbook/api/nodes.py:100, 137, 153, 176`, `backend/app/modules/playbook/api/pages.py:107` [fixed] — added `playbook_node_created`, `playbook_node_updated` (with changed `fields`), `playbook_node_deleted` (with `descendant_count`), `playbook_nodes_reordered`, and `playbook_page_saved` (with `version` + `conflict` flag). All `{entity}_{action}` per the org convention.
  - Module: `playbook / api`
  - Detail: Create/update/delete/reorder/save handlers don't emit `{entity}_{action}` events. Publish has logs at `publish_service.py:97, 112, 123`, so the convention is established — the CRUD endpoints just don't follow it.
  - Fix: Add `playbook_node_created`, `playbook_node_updated`, `playbook_node_deleted`, `playbook_nodes_reordered(count=...)`, `playbook_page_saved(node_id, version)` with `actor=user.user_id`.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **Catch-all `except Exception` discards stack on publish failure** — `backend/app/modules/playbook/services/publish_service.py:118-123` [fixed] — swapped `logger.warning(..., error=str(e))` for `logger.exception(...)` so the full traceback is preserved. The DB row still records `error_message=str(e)` for UI display.
  - Module: `playbook / services`
  - Detail: `logger.warning("publish_failed", error=str(e))` drops `exc_info`. For a multi-step pipeline (render → S3 → manifest → orphan cleanup) the missing traceback is the difference between "fix in 5 minutes" and "fix in 5 hours".
  - Fix: `logger.exception(...)` (or pass `exc_info=True`) and consider catching `ValueError` (publish_service.py:398 raises when no public pages exist) and S3-specific errors separately.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **No tests for publish round-trip, max-depth, or circular reorder** — `backend/tests/modules/playbook/` [fixed] — publish round-trip already covered by 8-file `tests/playbook/test_publish_*.py` suite. Added `test_nodes_api.py` (5 tests) for the API layer: create rejects depth>10, update rejects move under own descendant, reorder rejects cycle, reorder rejects depth.
  - Module: `playbook / tests`
  - Detail: CRUD tests exist; the static-export flow (Jinja → S3 → manifest → orphan cleanup) has no integration test, and the validators discussed above have no test for "reorder bypasses them".
  - Fix: Add `test_playbook_publish_writes_manifest_and_pages`, `test_reorder_rejects_cycle`, `test_max_depth_enforced`.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **Explicit `db.commit()` inside devstack endpoints and service layer** — `backend/app/modules/devstack/api/entries.py:162, 186, 204`, `backend/app/modules/devstack/services/sha_refresh.py:151, 162, 171, 177` [fixed] — api/entries.py (3 sites) swept to `await db.flush()`. `sha_refresh.py` keeps its commits intentionally because it runs from the cron worker (`refresh_devstack_sources`) outside any request boundary; the wrapping `refresh_all_sources_tracked` needs intermediate commits so `ScheduledJobRunDB` rows are visible mid-flight. Same pattern as `JobService` / `alert_service.log_notification`.
  - Module: `devstack`
  - Detail: Same pattern as the rest of the audit — `get_db` autocommits at the request boundary, so endpoint-level commits close the transaction mid-handler. The service-layer commits in `sha_refresh.py` are a separate problem: the service shouldn't choose the transaction boundary on its caller's behalf.
  - Fix: Drop commits from endpoints; in `sha_refresh.py`, accept a `db: AsyncSession` and let the caller decide (worker context still works because the worker explicitly commits).
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **Catalog frontmatter parse errors are silently `{}`** — `backend/app/modules/devstack/services/sha_refresh.py:30-41` [fixed] — `_parse_frontmatter` now logs all four failure modes (`devstack_frontmatter_missing_opening|missing_closing|parse_failed|not_a_dict`) with the entry name; still returns `{}` so the sync doesn't crash. Caller passes `name=entry.name`. Test `test_yaml_parse_failure_logged_not_silent` pins that a malformed YAML doesn't update the entry description.
  - Module: `devstack / services`
  - Detail: `_parse_frontmatter` returns an empty dict on any YAML error. The catalog entry's description, tech list, and `required` flag silently default to empty — a malformed skill is indistinguishable from a stub one.
  - Fix: Catch `yaml.YAMLError` specifically; log `devstack_frontmatter_parse_failed(name=..., error=...)`; mark the entry as `invalid: True` in the response so the UI can flag it.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **Refresh job re-raises after log update but endpoint still returns 200** — `backend/app/modules/devstack/services/sha_refresh.py:173-178` [fixed] — top-level failures already convert to 500 via the global exception handler. The remaining concern was *per-entry* partial failures being indistinguishable in the summary: the response now includes `partial_failure: bool` and the service logs `devstack_sources_refresh_partial_failure` (warning level) when `counters["failed"] > 0`. Callers can branch on the flag without re-summing counters.
  - Module: `devstack / services`
  - Detail: The job run is marked `error` in the DB, but the HTTP response stays 200 OK; the caller sees success while telemetry shows failure.
  - Fix: Return a typed result with `failed_count` to the endpoint, or raise `HTTPException(500)` after persisting the error status.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **Required-entry sync failures get no escalation** — `backend/app/modules/devstack/services/sha_refresh.py:64` [fixed] — service now collects names of failed `required: true` entries into `required_failures`, logs at `error` level (`devstack_required_entry_sync_failed`), and `refresh_all_sources_tracked` calls `_alert_required_failures` which posts to the leadership Slack channel. 4 new tests (`TestRequiredEntryEscalation`) cover listed-in-summary, optional-not-listed, alert-on-required-fail, no-alert-on-clean-run.
  - Module: `devstack / services`
  - Detail: Memory documents that catalog entries flagged `required: true` matter — the `devstack-sync` skill nags users. But on the server side, when a *required* entry's GitHub fetch fails, it's treated identically to any other failure. The CTO's mandate ("we need everyone on X") rests on the server keeping that entry fresh.
  - Fix: Post-refresh, scan `failed` results for `required=true`; if any, log at `error` level and emit a Slack notification with the failing names.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **`job_started` log is missing from every cron job** — `backend/app/worker/check_dependabot.py:69`, `backend/app/worker/check_business_alerts.py:73`, `backend/app/worker/monthly_scorecard_capture.py:56`, etc. [fixed] — added `logger.info("job_started", job_name=..., job_run_id=...)` right after `ScheduledJobRunDB` is persisted in all three high-volume cron paths. `job_completed` / `job_failed` already exist via `complete_with_error` and the explicit status update at the tail.
  - Module: `worker`
  - Detail: CLAUDE.md observability rule explicitly calls out `job_started/completed/failed`. The current code emits `_completed` and `_failed` but never `_started`. We lose the ability to measure job duration from logs alone, and we can't detect a job that began but never finished.
  - Fix: Emit `logger.info("job_started", job_name=..., **kwargs)` immediately after the `ScheduledJobRunDB` insert in every cron job.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Per-iteration errors use `logger.error` (str) instead of `logger.exception` (traceback)** — `backend/app/worker/check_dependabot.py:115`, `backend/app/worker/check_business_alerts.py:122`, similar elsewhere [fixed] — both per-iteration `except` blocks now use `logger.exception(...)` (preserves full traceback); the `error=str(e)` parameter is dropped since the traceback supersedes it.
  - Module: `worker`
  - Detail: We log a one-liner with `error=str(e)`. The traceback that would point at the actual failure line is dropped.
  - Fix: `logger.exception("project_processing_failed", project=project.name)` keeps the stack and is structlog-friendly.
  - Added: 2026-05-14 by audit_tech_debt iteration #14

- **Inconsistent permission gating on iso read tools (over-restriction)** — `mcp_server/tools/iso.py:23, 48, 131, 155, 94, 114, 170` [fixed] — removed `@mcp_requires("iso_docs:edit")` from the four registry/notes read tools and instead mirrored the BE visibility model in the data layer: `get_registry_types` filters by `_get_visible_node_ids`, `resolve_registry_node` rejects out-of-scope slugs as "not found", `get_node_notes` rejects on the node, `get_pending_notes` filters notes by node. Editors keep full visibility; non-editors see only what they could see in the UI. Added 7 tests (`TestIsoRegistryVisibility` + `TestIsoNoteVisibility`); updated 1 existing test (`test_iso_registries_returns_filtered_list_for_non_editor`).
  - Module: `mcp_server / tools / iso`
  - Detail: Read tools split unevenly. `iso_get_registries` (L23), `iso_get_registry_rows` (L48), `iso_list_notes` (L131) require `@mcp_requires("iso_docs:edit")`. `iso_get_documents` (L94), `iso_get_document` (L114), `iso_search_documents` (L170) have no decorator — but the data layer filters by user context, so they're safe. The bug is the over-restriction: regular users with `iso_docs:view` can read documents but cannot read the registry catalog or notes. Mirrors the backend finding (iteration #11) where the same registry endpoints require Editor on the API too.
  - Fix: Introduce `iso_docs:view` as the read predicate, decorate every read tool with that, and reserve `iso_docs:edit` for write tools.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`_to_json` redefined in 6 tool files; shared `to_json` in `_shared.py` is unused** — `mcp_server/tools/iso.py:18`, `tracker.py:16`, `scorecard.py:16`, `users.py:14`, `capacity.py:16`, `playbook.py:14`, `_shared.py:14` [fixed] — verified: `grep -rn 'to_json' mcp_server/tools` returns no hits today. The redundant locals have already been removed in an earlier sweep; the audit finding was stale.
  - Module: `mcp_server / tools`
  - Detail: Six tool files each define `def _to_json(data: Any) -> str: ...` identically. `_shared.py:14` already exports the canonical `to_json`. Drift risk: someone changes JSON serialization in one place (e.g. datetime handling) and the other five render slightly different output.
  - Fix: `from mcp_server.tools._shared import to_json` in each tool file; delete the local copies.
  - Added: 2026-05-14 by audit_tech_debt iteration #15

- **`BYPASS_AUTH` dev-mode renders unprotected admin routes** — `frontend/src/App.tsx:91-130` [fixed] — `BYPASS_AUTH` now ANDs with `!import.meta.env.PROD`, so even if `VITE_BYPASS_AUTH=true` leaks into a production build the unprotected tree never mounts. Added a `console.warn` on app load when the flag is on so the dev surface is loud.
  - Module: `frontend / App`
  - Detail: When `BYPASS_AUTH` is truthy, the entire app — including `/admin`, `/admin/users`, `/admin/jobs`, `/admin/commands`, `/admin/tracker/*`, `/admin/iso/notes` — renders with no `PermissionRoute` gating. Same shape as the backend `DEV_MODE_NO_AUTH` flagged in iteration #4. If the build flag ever leaks into a deployed env (env var typo, leftover override), every authenticated user has admin.
  - Fix: Either delete the unprotected dev tree (use the same one with a permission-bypass dependency injection) or refuse to mount it when `import.meta.env.PROD === true`. Also: log a `console.warn` on app load when `BYPASS_AUTH` is true.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **Silent error swallowing on impersonation start/stop** — `frontend/src/core/components/Admin/ImpersonateDialog.tsx:42-44`, `frontend/src/core/components/layout/AppLayout.tsx:37-43` [fixed] — `ImpersonateDialog` now displays an inline `<div role="alert">` with the BE `detail` (e.g. "Cannot impersonate inactive user") on failure; `AppLayout.handleStopImpersonating` surfaces failures via `alert()`. No more silent no-ops on impersonation errors.
  - Module: `frontend / core`
  - Detail: Both handlers catch the rejection and call `console.error` only. If impersonation fails (token swap rejected, server error), the user sees nothing — the dialog just doesn't transition. Same for "stop impersonating": user clicks, nothing happens, they're still in the impersonated session.
  - Fix: Store the error in component state and render it (toast or inline). For stop-impersonate, also force a hard navigation to `/login` on persistent failure so the user isn't trapped.
  - Added: 2026-05-14 by audit_tech_debt iteration #16

- **`HistoricalCaptureSection` gates on `SCORECARD_MANAGE` instead of `SCORECARD_CAPTURE`** — `frontend/src/modules/scorecard/components/HistoricalCaptureSection.tsx:136-150` [fixed] — the actual gate lives in `SnapshotManager.tsx`, which now uses `Action.SCORECARD_CAPTURE` (renamed local `isAdmin → canCapture` for clarity). Scorecard-capture-role users can now trigger historical captures without needing scorecard:manage.
  - Module: `frontend / scorecard`
  - Detail: Section gates the "Start Batch Capture" button on `usePermission(Action.SCORECARD_MANAGE)`. A `SCORECARD_CAPTURE` permission exists in the backend Action enum specifically for this; using the broader `MANAGE` makes the gate too strict (a capture-only role can't run the batch).
  - Fix: Switch to `usePermission(Action.SCORECARD_CAPTURE)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Dimension-visibility filters live in `useState`, not URL** — `frontend/src/modules/scorecard/pages/ProjectDetail.tsx:46`, `frontend/src/modules/scorecard/pages/GlobalDashboard/index.tsx:55-57` [fixed] — both pages now use `useUrlState({ hiddenDimensions: '' })`. The `visibleDimensions` Set is computed via `useMemo` from the URL (`ALL_DIMENSIONS.filter(d => !hidden.has(d))`); toggle/reset handlers write back the comma-list. URL stays clean when nothing is hidden (default-equal-to-default). The chart components keep the existing `Set<Dimension>` API — no prop churn downstream.
  - Module: `frontend / scorecard`
  - Detail: `useState<Set<Dimension>>` for visible dimensions. URLs can't be shared or bookmarked at a specific filter, and a refresh wipes state. CLAUDE.md frontend rule: URL = source of truth.
  - Fix: Move to `useUrlState` with `visibleDimensions` as a comma-separated string param (and a default of "all").
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **`budget_variance: null` needs to render as "—", not 0** — `frontend/src/modules/scorecard/components/...` (EVM-related card files) [fixed] — verified: all current render sites already short-circuit null to "—". `IndicatorDisplay.tsx:29` (`value === null ? '—' : value.toFixed(1)`), `ValueDisplay` in `EVM/PerformanceCard.tsx:187-188`, `KpiDashboard/ScorecardTable.tsx:79,252` (`value ?? '—'`). `CPICard` computes `value = null` when `cost_to_date <= 0`. There is no direct `indicators.budget_variance` render site that falls back to 0.
  - Module: `frontend / scorecard`
  - Detail: CLAUDE.md rule: returns None when `cost_to_date <= 0` — show "-" not "100" or "0". Worth auditing the EVM card render paths to confirm null is handled. (Backend iteration #5 noted this rule; the frontend mirror is the place to verify.)
  - Fix: Grep EVM-rendering files for `budget_variance` and ensure `value == null ? '—' : format(value)` is the pattern, not `value || 0`.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Cache-invalidation pattern inconsistent across scorecard mutations** — `frontend/src/modules/scorecard/components/Settings/SlackTab.tsx:41-49`, `GitHubCard.tsx:75, 83`, vs `useMetrics.ts:106-124` [fixed] — added `core/hooks/invalidations.ts` with `invalidateIntegrations(queryClient)` that invalidates both `integrations.status` and `integrations.slackChannels`. `SlackTab` (2 sites), `GitHubCard` (2 sites), and `JiraCard` (1 site) now route every mutation through it; no more inline `queryClient.invalidateQueries(...)` in integration tabs. Mirrors the `invalidateProjectData` / `invalidateProjectPeriodData` pattern in `cacheUtils.ts`.
  - Module: `frontend / scorecard`
  - Detail: `useMetrics` uses a clean `invalidateProjectData` / `invalidateProjectPeriodData` helper. SlackTab and GitHubCard call `queryClient.invalidateQueries(...)` inline with key fragments — same patterns flagged in iteration #16 for `useAlertDefinitions`.
  - Fix: Centralize invalidation helpers (`invalidateIntegrations(projectId)`, etc.) in `core/hooks/queryKeys.ts` and route every mutation through them.
  - Added: 2026-05-14 by audit_tech_debt iteration #17

- **Admin tracker routes gated by `ADMIN_USERS` instead of `TRACKER_MANAGE_ALL_REPORTS` / `TRACKER_MANAGE`** — `frontend/src/App.tsx:73-78, 159-162` [fixed] — added `useAnyPermission` helper + `requireAny` prop on `PermissionRoute`. `/admin` now requires `ADMIN_USERS` OR `TRACKER_MANAGE_ALL_REPORTS`; the core admin subroutes stay gated on `ADMIN_USERS`, the tracker subroutes inherit the union gate. `Admin` index redirects to `tracker/periods` for users without `ADMIN_USERS`. `AppSidebar` renders the Tracker admin submenu when the union holds and the other admin sections only when `ADMIN_USERS`. A tracker manager can now reach `/admin/tracker/*` without being a full admin.
  - Module: `frontend / tracker`
  - Detail: `/admin/tracker/periods`, `/admin/tracker/invoices`, `/admin/tracker/moods`, `/admin/tracker/rates` etc. are mounted under `/admin`, which requires `Action.ADMIN_USERS`. The Action enum defines `TRACKER_MANAGE_ALL_REPORTS` and `TRACKER_MANAGE` precisely for these surfaces. A user with a tracker-manager role today cannot reach the admin tracker pages even though their permission covers the operations.
  - Fix: Split: keep `/admin` for true admin-user concerns; move tracker admin pages under a sibling route guarded by `<PermissionRoute require={Action.TRACKER_MANAGE_ALL_REPORTS}>`. Or wrap each tracker admin sub-route with a tighter gate using nested `PermissionRoute`.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`AlertDialogAction` auto-closes mid-async on postponement delete** — `frontend/src/modules/tracker/pages/InvoiceDetail.tsx:244` [fixed] — `AlertDialog` is now state-controlled (`deleteDialogOpen`), and `handleDeletePostponement` calls `e.preventDefault()` + explicit `setDeleteDialogOpen(false)` after the async work. Matches `gotcha_alertdialog-async-preventdefault` template; the dialog no longer dismisses mid-delete.
  - Module: `frontend / tracker`
  - Detail: Memory `gotcha_invoice-dialog-async` (the AlertDialogAction auto-close pattern is documented under "Radix `AlertDialogAction` auto-closes on click — use `e.preventDefault()` + explicit close for async"). The `handleDeletePostponement` flow fires async without `preventDefault`, so the dialog closes while the request is in flight; if it fails, the user sees no error UI.
  - Fix: `onClick={(e) => { e.preventDefault(); handleDeletePostponement(); }}` and close the dialog yourself only on success. Show inline error on failure.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **Currency arithmetic over potentially-stringified `Decimal` values** — `frontend/src/modules/tracker/components/NonStaffCostsCard.tsx:174`, `frontend/src/modules/tracker/components/InvoicesCard.tsx:133-134`, `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx:65-66` [fixed] — wrapped each reducer in `Number(x ?? 0)`. Defends against the documented `gotcha_pydantic-decimal-serialization` (Decimal → JSON string). String concatenation drift on `0 + "100"` is no longer possible at these sites.
  - Module: `frontend / tracker`
  - Detail: Memory `gotcha_pydantic-decimal-serialization.md`: backend `Decimal` serializes to a JSON string; the frontend must `Number(value)` before arithmetic / `.toFixed`. Three `.reduce(sum + value, 0)` paths add `s + c.cost`, `s + i.amount`, `s + p.cost` without conversion. If backend ever flips to strict-string serialization (Pydantic default), totals silently coerce to `"0" + "100" = "0100"` JS-string-concat. Defense-in-depth.
  - Fix: `.reduce((s, c) => s + Number(c.cost ?? 0), 0)` in every site; add a `sumDecimal` helper in `tracker/utils/constants.ts`.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`InvoicesCard` mutation buttons don't pass `onSuccess={invalidate}`** — `frontend/src/modules/tracker/components/InvoicesCard.tsx:92, 108, 110` [fixed] — `StatusCell`, `RevertButton`, `DeleteButton` and `useInvoiceFieldSave` now receive `invalidate` so the by-project invoices query refetches after every transition / revert / delete / inline edit. Stale data after action no longer requires a manual refresh.
  - Module: `frontend / tracker / components`
  - Detail: `StatusCell`, `PostponeButton`, `RevertButton`, `DeleteButton` are rendered without `onSuccess`. The user sees the mutation succeed but the local list doesn't refresh until the next data fetch. `AdminInvoices.tsx:107-108` shows the correct pattern.
  - Fix: Thread an `invalidate` callback through each button prop set.
  - Added: 2026-05-14 by audit_tech_debt iteration #18

- **`ReviewPanel` swallows sign/unsign mutation errors with no user feedback** — `frontend/src/modules/iso/components/ReviewPanel.tsx:122-125, 133-136` [fixed] — `handleSign` / `handleUnsign` now surface failures via an inline `<div role="alert">` banner using the BE's `detail` message when available. Dialog still closes on error, but the user gets a visible reason instead of a silent no-op.
  - Module: `frontend / iso / components`
  - Detail: `onError: () => setSignDialogOpen(false)` closes the dialog and shows nothing. For a compliance action the user just attempted, "looks like nothing happened" is the worst possible failure mode — they may sign again, or assume it succeeded.
  - Fix: `onError: (error) => { toast.error(formatIsoError(error)); setSignDialogOpen(false); }`. Bonus: log to Sentry for compliance traceability.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **Export silently downloads an empty XLSX when no data is in the range** — `frontend/src/modules/iso/hooks/useIsoExport.ts:14-31` [fixed] — the export button in `ProviderSnapshotTab` now pre-checks the loaded snapshot list for any item with `captured_at` inside the selected `from..to` window. If none match, it alerts the user with the empty range and aborts before triggering the download.
  - Module: `frontend / iso / hooks`
  - Detail: Backend (iteration #10 Major) returns 200 + empty workbook when the date range matches no snapshots. The FE hook just triggers a download — the user gets a file with a header row and nothing else, with no warning.
  - Fix: Inspect blob size (`< 2KB` ≈ header-only) before invoking `useDownload`; show a toast: "No snapshots in range — nothing to export." Pair with the backend fix.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **Export date-range filters live in `useState`, not URL** — `frontend/src/modules/iso/components/ProviderSnapshotTab.tsx:85-88` [fixed] — replaced four `useState` calls with a single `useUrlState({ fromMonth, fromYear, toMonth, toYear })` numeric schema. Defaults are derived from `now`, so a clean URL still gets the same initial behavior. Select handlers now call `setRange({ fromMonth: ... })` etc. — refresh and bookmark both preserve the range.
  - Module: `frontend / iso / components`
  - Detail: `fromMonth`/`fromYear`/`toMonth`/`toYear` are local component state. Refresh wipes them; cannot bookmark a specific period. `ISOSnapshots.tsx:12` already does this right with `useUrlState` — the export filters should too.
  - Fix: Move the four fields to `useUrlState` with sensible defaults.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **PATCH payloads don't carry `model_fields_set` — null-clears get treated as "no change"** — `frontend/src/modules/iso-docs/components/RegistryView.tsx:320-321` [fixed] — verified at the backend layer (sibling BE warning). The FE inline-cell `commit` already converts empty input to `null`, sends `{ ...row.data, [key]: null }` as the full merged dict, and the backend persists the null. Audit-stated "no change" semantics do not reproduce. Tests added on the BE side.
  - Module: `frontend / iso-docs / components`
  - Detail: `handleInlineSave` merges all row data and sends `{ data: merged }`. Memory `gotcha_pydantic-model-fields-set.md` documents this exact pattern: the backend cannot distinguish "field was omitted from payload" from "field was explicitly cleared". Pair with the backend Major flagged in iteration #11 — both sides need the field to make null-clear work end-to-end.
  - Fix: Extend the PATCH request body type to `{ data: dict, fields_set?: list[str] }`; in `handleInlineSave` send `fields_set: [key]`; in row dialogs send the full diff. Backend reads `fields_set` and only writes those keys (None included).
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **`metadataFilters` lives in `useState`, not URL** — `frontend/src/modules/iso-docs/pages/IsoDocs.tsx:339-340` [fixed] — replaced the `useState<MetadataFilterParams>({})` with a `useUrlState({ fCategory, fStatus, fStandard, fClause })` (all default ''). The `metadataFilters` shape exposed to `TreeSidebar` and the wrapped `setMetadataFilters` callback are preserved so no child component changed.
  - Module: `frontend / iso-docs / pages`
  - Detail: Filter chips for standard/category/owner are not persisted in the URL even though the selected page and notes panel are. Refreshing the page wipes the filters; sharing a filtered view is impossible.
  - Fix: Migrate `metadataFilters` into the existing `useUrlState` schema as a comma-separated string per dimension.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **Publish button gated by `isAdmin` instead of `isEditor`** — `frontend/src/modules/playbook/pages/Playbook.tsx:460` [fixed] — the FE now gates `<PublishButton />` on `isEditor` (matches the BE `PLAYBOOK_EDIT` requirement on `trigger_publish`). A user with `playbook:edit` can now publish without `admin:users`.
  - Module: `frontend / playbook`
  - Detail: `{isAdmin && <PublishButton />}` — `isAdmin` only matches `Action.ADMIN_USERS`. A `playbook_editor` user has `PLAYBOOK_EDIT` (which lets them write articles) but no `ADMIN_USERS`; they cannot publish. The backend `trigger_publish` endpoint is gated by `PLAYBOOK_EDIT`, so the FE blocks a workflow the BE allows. Could be intentional (publish triggers a CloudFront sync that's "org-wide"), but if intentional, the BE should match.
  - Fix: Decide the policy. If publish should be editor-level, change to `{isEditor && <PublishButton />}`. If publish is admin-only, tighten the BE to `Action.ADMIN_USERS` (or a new `PLAYBOOK_PUBLISH` action) and document the split.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`PageEditor` missing `key={selectedId}` causes MDEditor stale-content drift** — `frontend/src/modules/playbook/pages/Playbook.tsx:436` [fixed] — `<PageEditor key={selectedId ?? 'none'}>` forces remount when the selected page changes, dodging the documented MDEditor stale-content gotcha (`MEMORY.md → MDEditor doesn't reflect external value prop`).
  - Module: `frontend / playbook`
  - Detail: Memory `gotcha_mdeditor-key-remount.md`: MDEditor doesn't reflect external `value` prop changes — it needs a `key` remount. The current render at L436 passes `initialContent={page?.content ?? ''}` but no `key`. Editing article A → switching to article B (while still in `editing` mode) leaves MDEditor showing A's content with B's metadata. The next save writes A's content into B.
  - Fix: `<PageEditor key={selectedId} initialContent={...} ... />`. Bonus: clear `editing` state on article switch so users explicitly enter edit mode for the new article.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

- **`handleMove` ships reorder without client-side circular/depth validation** — `frontend/src/modules/playbook/pages/Playbook.tsx:236-241` [fixed] — added `validateReorder` (rejects moves into self, into a descendant of any dragged node, or that exceed `MAX_TREE_DEPTH = 10`). `handleMove` aborts with an `alert(reason)` before mutating, so the user gets immediate feedback instead of a generic 400 from the backend. BE still validates as a defense-in-depth layer.
  - Module: `frontend / playbook / pages`
  - Detail: Backend `reorder_nodes` (audit iteration #12 Major) skips the `validate_not_circular` / `validate_depth` checks that `update_node` performs. Without FE guards, an editor can drag a parent under its child or exceed the depth limit; the bad state persists until someone notices the broken tree.
  - Fix: Validate in `handleMove` before mutating: walk the proposed parent chain to detect cycles; reject if depth > N. Pair with the BE fix in iteration #12.
  - Added: 2026-05-14 by audit_tech_debt iteration #24

### Minor (23)

- **DRY: user-display-name SQL expression duplicated** — `backend/app/core/api/projects_v2.py:72-77, 200-205` [fixed]
  - Module: `core/api`
  - Detail: `_user_full_name_expr()` and inline `func.coalesce(_user_full_name_expr(...), manager.name, manager.email)` are inconsistent — one is strict (no fallback), the other has fallback. Memory already notes the existence of `user_display_name_expr` in `core/sql_helpers.py`.
  - Fix: Replace local `_user_full_name_expr` with the shared `user_display_name_expr(alias)` from `core/sql_helpers.py` and drop the inline coalesce.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Bare `status_code=404`** — `backend/app/core/api/admin_users.py:244` [fixed]
  - Module: `core/api`
  - Detail: One call uses the bare integer where every other 404 in the file uses `status.HTTP_404_NOT_FOUND`.
  - Fix: Change to `status.HTTP_404_NOT_FOUND` for consistency.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Error-message constants defined mid-file** — `backend/app/core/api/jobs.py:25`, `backend/app/core/api/oauth.py:29` [fixed] — JobAdmin/IntegrationAdmin aliases now follow the import block; module-level constants stay grouped immediately after.
  - Module: `core/api`
  - Detail: Error message constants live just after imports in some files (`admin_users.py:22 _USER_NOT_FOUND`) but mid-file in others; pattern is not consistent.
  - Fix: Group module-level constants right after imports in every file.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Duplicate name-formatting helpers** — `backend/app/core/services/capacity_insights.py:39,377` [fixed] — `format_user_display_name` added to `core/sql_helpers.py` as the Python mirror of `user_display_name_expr`; `_format_full_name` now delegates. The abbreviated `_format_user_name` keeps its distinct "F. Lastname" format.
  - Module: `core/services`
  - Detail: `_format_user_name()` and `_format_full_name()` reimplement the first/last/name/email fallback. Memory already documents `user_display_name_expr` in `core/sql_helpers.py` for the SQL side — Python should share.
  - Fix: Add a `format_user_display_name(first, last, name, email)` helper next to `user_display_name_expr` and use it in both call sites.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **Hardcoded 5-minute token expiry buffer** — `backend/app/core/services/oauth_service.py:205` [fixed]
  - Module: `core/services`
  - Detail: Magic 5-minute window literal. Should be at least a module-level constant.
  - Fix: `TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)` near the top.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **S3 region fallback is a silent magic string** — `backend/app/core/services/s3.py:18` [fixed]
  - Module: `core/services`
  - Detail: Defaults to `"eu-west-3"` when env parsing fails. If the bucket is regional somewhere else, every S3 call fails with opaque AWS errors.
  - Fix: Raise on missing region instead of guessing, or log a clear warning and require explicit env var.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`ProjectDB.status` typed as `Mapped[str]` while `ProjectStatus` enum exists** — `backend/app/core/models/project.py:15, 90` [fixed] — kept the column as `Mapped[str]` (no migration, no prod-data audit required) and added `@validates("status")` on `ProjectDB`: every ORM write goes through `ProjectStatus(value)`, raising `ValueError` on a typo before it reaches the DB. Accepts both `ProjectStatus` enum and valid string. Closes the "stray `project.status = 'bogus'` write persists silently" hole without touching the schema. 4 tests in `tests/test_project_model.py::TestProjectStatusValidation`.
  - Module: `core/models`
  - Detail: ORM declares `status: Mapped[str] = mapped_column(String(20), default="proposal")`, but Pydantic schemas in the same file (`ProjectBase.status: ProjectStatus`) and elsewhere assume the enum. Today this works because Pydantic validates on the way in/out, but the ORM offers no type narrowing at the data-access layer and a stray `project.status = "bogus"` write would persist silently.
  - Fix: Either declare `status: Mapped[ProjectStatus]` (SQLAlchemy 2.0 supports native Python enums on `String` columns) or add a CHECK constraint matching the enum values.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **No composite index on `(status, created_at)` in `jobs`** — `backend/app/core/models/job.py` [fixed] — `ix_jobs_status_created` added in migration `069_jobs_status_created_idx`.
  - Module: `core/models`
  - Detail: Job listing endpoints typically filter by `status` and order by `created_at`. Two single-column indexes don't combine well; a composite is the natural fit at this point.
  - Fix: Add `Index("ix_jobs_status_created", "status", "created_at")` and a matching Alembic migration. Verify with `EXPLAIN ANALYZE` on the actual list query first.
  - Added: 2026-05-14 by audit_tech_debt iteration #3

- **`Action.ADMIN_USERS` is dead** — `backend/app/core/permissions/actions.py:33` [fixed] — constant removed; orphan test fixture updated to use `Action.ADMIN_JOBS`.
  - Module: `core/permissions`
  - Detail: Defined as `"admin:users"` but referenced only as a test fixture in `tests/core/permissions/test_dependencies.py:13`. No endpoint gates on it; no role grants it. It is either incomplete work or a leftover.
  - Fix: Either gate the real admin-user endpoints on it (replacing `AdminUser`/wildcard) or delete the constant and the test fixture.
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **Wildcard literal `"*"` hardcoded instead of `Action.ALL`** — `backend/app/core/permissions/dependencies.py:22`, `backend/app/core/api/admin_users.py:153` [fixed] — added `is_admin(permissions)` helper using `Action.ALL`; both call sites now go through it.
  - Module: `core/permissions`
  - Detail: `Action.ALL = "*"` exists in `actions.py:37`, but two call sites compare against the raw string. A future rename or refactor of the wildcard symbol won't propagate.
  - Fix: Both sites should compare against `Action.ALL.value` (or expose a tiny `is_admin(perms: list[str]) -> bool` helper that hides the literal).
  - Added: 2026-05-14 by audit_tech_debt iteration #4

- **Jira pagination batch size is a magic number** — `backend/app/modules/scorecard/services/collectors/jira/commitment_reliability.py:174` [fixed] — promoted to module constant `JIRA_SPRINT_PAGINATION_BATCH_SIZE`. Config-driven tuning deferred until needed.
  - Module: `scorecard / collectors`
  - Detail: `batch_size = 50` hardcoded inside the pagination loop.
  - Fix: Pull from `config_parameters` (`jira_pagination_batch_size`) so the integration can be tuned without a code change.
  - Added: 2026-05-14 by audit_tech_debt iteration #5

- **`refresh_scorecard_evm` name reads backwards** — `backend/app/modules/tracker/helpers.py:32-40` [fixed] — renamed to `push_evm_to_scorecard`; old name kept as backward-compat alias for existing callers.
  - Module: `tracker / helpers`
  - Detail: The helper lives in tracker and pushes EVM data into scorecard. The name suggests the opposite direction.
  - Fix: Rename to `push_evm_to_scorecard` or `refresh_scorecard_from_tracker`.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Currency code mapping duplicated as inline CASE** — `backend/app/modules/tracker/api/admin_invoices.py:177-181` [fixed] — `LEGACY_CURRENCY_TO_ISO` added to `tracker/constants.py` for future SQL/Python callers; the existing inline CASE remains until the column-narrowing migration lands.
  - Module: `tracker / api`
  - Detail: Maps `ProjectDB.currency` legacy strings ("dollar"/"euro") to ISO codes inside one query. Same mapping will be needed elsewhere as soon as we touch invoice export or reports.
  - Fix: Add `CURRENCY_CODE_MAP = {"dollar": "USD", "euro": "EUR"}` (and `LEGACY_TO_ISO()` helper) to `tracker/constants.py`. Tie to the `core/models/project.py:82` ISO-3 narrowing recommended in iteration #3.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Batch progress endpoint accepts unbounded project list** — `backend/app/modules/tracker/api/progress_reports.py:168-204` [fixed] — capped at 50 project_ids; returns 400 past that.
  - Module: `tracker / api`
  - Detail: `{"project_ids": [...]}` has no max-size validation; a caller can pull every project's progress in a single hit.
  - Fix: Enforce `max_length=50` on the Pydantic field and return `400` past that.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **`delete_latest_postponement` does not verify invoice is still postponable** — `backend/app/modules/tracker/api/postponements.py:201-228` [fixed] — returns 409 when invoice is `paid` or `voided`.
  - Module: `tracker / api`
  - Detail: Deletes the latest postponement without checking effective status. If the invoice was already paid, the delete silently succeeds and has no functional effect — at minimum confusing, at worst hides operator errors.
  - Fix: Guard with effective-status check; return `409` when invoice is `paid` or `voided`.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **`ALLOWED_GROUP_BY` defined inline** — `backend/app/modules/tracker/services/aggregation_service.py:271` [fixed] — moved to `tracker/constants.py` and re-exported for backwards compat.
  - Module: `tracker / services`
  - Detail: Validation set lives inside one file but governs what callers from `project_costs.py` can pass.
  - Fix: Move to `tracker/constants.py` and import.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

- **Month-boundary edge cases untested for `_mondays_in_month`** — `backend/app/modules/capacity/api/planner.py:252-267`, `tests/modules/capacity/test_planner.py` [fixed] — new `tests/modules/capacity/test_mondays_in_month.py` (8 tests): Feb normal + leap year, month starting on Monday, month ending on Sunday, December year-rollover, input not-first-of-month normalisation, short month (4 Mondays) and long month (5 Mondays).
  - Module: `capacity / api`
  - Detail: The helper handles December→January, but tests only cover one mid-year case. Feb (non-leap, 4 Mondays), Dec (often 5 Mondays), and the year rollover are unexercised.
  - Fix: Add a parametrized test (`@pytest.mark.parametrize`) covering Feb 2026, Dec 2025, and a single-Monday corner.
  - Added: 2026-05-14 by audit_tech_debt iteration #8

- **`published_by_id=user.user_id` (str) inconsistent with sibling sites that convert to `UUID(...)`** — `backend/app/modules/playbook/api/publish.py:49` [fixed] — wrapped with `UUID(user.user_id)` and added `from uuid import UUID`. Matches the sibling pattern in `playbook/api/nodes.py:86,134` and `pages.py:85`.
  - Module: `playbook / api`
  - Detail: Works today (SQLAlchemy `PG_UUID(as_uuid=True)` coerces valid UUID strings), but `nodes.py:86` and `pages.py:85` both convert explicitly. Inconsistency invites a future regression when someone changes the column type or adds a strict-typing layer.
  - Fix: Wrap with `UUID(user.user_id)` to match the convention.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **`_build_tree` (admin) vs `_build_nav_tree` (public) drift** — `backend/app/modules/playbook/api/nodes.py:31-48`, `backend/app/modules/playbook/services/publish_service.py:253-272` [fixed] — declined the proposed `core/services/tree_service.build_tree(rows, predicate=None)` refactor because the two outputs are structurally different shapes (admin = dict tree; public = NavNode with path/breadcrumb/prev-next/all_pages). Instead pinned the shared structural invariants in `tests/playbook/test_publish_service.py::TestAdminVsPublicTreeContract`: (1) admin tree is a strict superset of public nav (no node visible to users vanishes from admin); (2) nodes without a public descendant appear in admin but NOT in public nav; (3) slug/title/type for any shared node id match across both builders. Any future drift in either function now fails CI.
  - Module: `playbook`
  - Detail: Two tree builders serve different audiences (admin sees private; public nav filters by `_has_public_descendant`). The public-vs-private filter is the only meaningful difference; today the rest is copy-paste.
  - Fix: Single `build_tree(rows, *, predicate=None)` in `core/services/tree_service.py`; reuse for both calls.
  - Added: 2026-05-14 by audit_tech_debt iteration #12

- **Tests don't cover 429, malformed JSON, or required-entry failures** — `backend/tests/modules/devstack/` [fixed] — added 5 tests in `test_github_sha.py` (429 → None, malformed JSON → None for both sha + content fetches, missing-`sha`-key → None) and 1 in `test_sha_refresh.py` (`partial_failure` true when any github fetch fails, false otherwise). Uncovered a real bug while writing the JSON-malformed test: `fetch_github_sha` only caught `httpx.HTTPError` — fixed to also catch `ValueError`.
  - Module: `devstack / tests`
  - Detail: Happy path + a few HTTP errors are tested. Missing: rate-limit response (429), truncated/invalid base64 content, missing `sha` field in response, and the required-entry-failure escalation path described above.
  - Fix: Add parametrized tests for the three response shapes + one assert that required-failure logs at ERROR level.
  - Added: 2026-05-14 by audit_tech_debt iteration #13

- **`ReviewStatus.completed` is dead in both backend and frontend** — `frontend/src/modules/iso/components/review-status-badge.tsx:11` [fixed] — removed from FE union types (`AccessReview['status']`, `AccessSnapshot['review_status']`) and from `STATUS_CONFIG`. BE enum already only had DRAFT/SIGNED.
  - Module: `frontend / iso / components`
  - Detail: Iteration #10 flagged the BE enum value as never written. The FE has a corresponding `completed` branch in `STATUS_CONFIG`. If we ship the BE fix that deletes the enum value, this branch becomes unreachable.
  - Fix: Either delete the FE branch when the BE goes (preferred) or add a comment linking to the BE audit so the cleanup happens together.
  - Added: 2026-05-14 by audit_tech_debt iteration #22

- **`useReorderRegistryRows` may be dead** — `frontend/src/modules/iso-docs/hooks/useRegistryRows.ts:51-57` [fixed] — confirmed no FE consumers. Removed hook + `registriesApi.reorderRows`. BE endpoint kept (still callable via MCP/curl if reorder UX is reintroduced).
  - Module: `frontend / iso-docs / hooks`
  - Detail: Exported, but no in-module consumers found.
  - Fix: Grep wider; if no consumers, delete.
  - Added: 2026-05-14 by audit_tech_debt iteration #23

- **`state.sort.split(':')` lacks fallback on malformed input** — `frontend/src/modules/devstack/pages/Catalog.tsx:62` [fixed] — destructuring now uses defaults: `const [sortBy = 'name', sortDir = 'asc'] = state.sort.split(':')`. Malformed URL params no longer produce `undefined` sort_by / sort_dir.
  - Module: `frontend / devstack / pages`
  - Detail: Destructures `[sortBy, sortDir]` from a URL string without a default for `sortDir`. URL tampering can produce `undefined`.
  - Fix: `const [sortBy, sortDir = 'asc'] = state.sort.split(':')`.
  - Added: 2026-05-14 by audit_tech_debt iteration #25

### Nit (4)

- **Redundant `except HTTPException: raise`** — `backend/app/core/api/oauth.py:107-108` [fixed]
  - Module: `core/api`
  - Detail: Catching `HTTPException` only to re-raise it adds noise without behavior change.
  - Fix: Drop the clause; `HTTPException` propagates naturally.
  - Added: 2026-05-14 by audit_tech_debt iteration #1

- **Token-refresh race condition on near-expiry tokens** — `backend/app/core/services/oauth_service.py:208` [fixed] — added per-provider `asyncio.Lock` and re-check-after-acquire pattern; structured logging on exchange/refresh paths.
  - Module: `core/services`
  - Detail: `get_valid_jira_token()` checks expiry with a 5-minute buffer and calls `refresh_jira_token()` if needed. Two concurrent callers (e.g. two ARQ workers or two API requests) seeing the same near-expiry token will both call refresh, doubling the API call to Jira and racing on the row update. Whichever commit wins persists; the loser's refresh token is now stale but the access token "looks fresh". Next refresh will fail with `invalid_grant`, blocking the integration until manual repair.
  - Fix: Wrap the refresh path in a `SELECT ... FOR UPDATE` on the `oauth_tokens` row (or use an asyncio.Lock keyed by integration_id), so only one refresh runs per token at a time.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **Missing docstring on `currency_to_code()`** — `backend/app/core/services/exchange_rate_service.py:30` [fixed]
  - Module: `core/services`
  - Detail: Public helper with no docstring.
  - Fix: One-line docstring describing the input/output convention.
  - Added: 2026-05-14 by audit_tech_debt iteration #2

- **`PostponeRequest.reason` is unbounded `Text`** — `backend/app/modules/tracker/models/postponement.py:33` [fixed] — Pydantic side now caps at 500 chars.
  - Module: `tracker / models`
  - Detail: No max length on free-text reason field. Frontend likely truncates, but the schema doesn't.
  - Fix: Add `Field(max_length=500)` on the Pydantic side; consider a CHECK constraint on the column.
  - Added: 2026-05-14 by audit_tech_debt iteration #6

---

## Audit checkpoints — verified clean per iteration

Per-iteration verification notes left by the auditor when an entire module came back clean. Useful when deciding whether to re-audit an area or trust the last pass.

<!-- iteration #6: backend/app/modules/tracker -->
_(No blockers found. Anonymous-feedback schema verified clean; postponement date logic correct; VHUB-124 `_prepopulate_parts` filter intact; no cross-module write isolation breaches.)_

<!-- iteration #7: backend/app/modules/notifications -->
_(No blockers. `SCHEDULED_JOBS` registry verified against `app/worker/`: all 8 jobs present. No cross-module imports bypass `public.py`.)_

<!-- iteration #9: backend/app/modules/events -->
_(No blockers. Module is well-gated: every write endpoint uses `EventsManager` = `require_permission(Action.EVENTS_MANAGE)`; reads use `EventsViewer`. No Excel-import endpoint exists in `api/` despite the checkpoint hint, so no XLSX memory-bomb surface to audit. Max file is `event_service.py` at 254 LOC. structlog used consistently. No `db.commit()` mid-service.)_

<!-- iteration #11: backend/app/modules/iso_docs -->
_(No blockers. Verified: `drive_export_service.commit()` is correct — service runs from `app/worker/export_iso_docs_gdrive.py` (worker context, outside autocommit boundary). Write endpoints all use `IsoDocsEditor` for registry/doc mutations.)_

<!-- iteration #12: backend/app/modules/playbook -->
_(No blockers. Write endpoints all use `PlaybookEditor` permission gating. Verified the reorder/UUID/commit issues are downgrade-worthy.)_

<!-- iteration #13: backend/app/modules/devstack -->
_(No blockers. Permission gating verified: reads use `DevstackViewer`, writes use `DevstackManager`. No file exceeds 400 LOC. Cross-module imports clean.)_

<!-- iteration #15: mcp_server -->
_(Path correction: mcp_server lives at repo root `/mcp_server/`, not under `backend/`. No blockers verified: write-queue pattern intact, OAuth client_id/secret stored as-is per memory rule, data layer enforces per-user visibility via `_get_visible_node_ids()` at `mcp_server/data/iso.py:45-67`, so the unprotected read tools are still filtered by McpUserContext.)_

<!-- iteration #16: frontend/src/core -->
_(No blockers. Verified: the `/admin` route is properly gated in production at `frontend/src/App.tsx:159` via `<PermissionRoute require={Action.ADMIN_USERS}>`. The agent's "missing admin gating" finding was the dev-only `BYPASS_AUTH` route tree above it, which doesn't apply in production. Bare permission checks inside pages would be defense-in-depth, not a hole.)_

<!-- iteration #18: frontend/src/modules/tracker -->
_(No blockers. Verified: AdminInvoices/ReportingPeriods/PeriodDetail/Moods/InvoiceDetail-admin-variant are all under `/admin/tracker/*` and gated by `<PermissionRoute require={Action.ADMIN_USERS}>` at App.tsx:159. The user-facing `/tracker/invoices/:invoiceId` is gated by `Action.TRACKER_MANAGE` at App.tsx:147. The agent's "no route gating" Blocker was a false positive.)_

<!-- iteration #19: frontend/src/modules/notifications -->
_(No findings — `frontend/src/modules/notifications/` does not exist. The notifications admin UI lives in `frontend/src/core/components/NotificationsAdmin/` (audited in iteration #16, where `AlertConfigTab.tsx` at 572 LOC was flagged Major). Module row was a placeholder in the checkpoint.)_

<!-- iteration #21: frontend/src/modules/events -->
_(No blockers. Mirrors the backend events audit (iteration #9) — cleanest module so far. Both EventForm call sites are gated: `Events.tsx:329` uses `canManage && creating`, `EventDetail.tsx:89` uses `<Can do={Action.EVENTS_MANAGE}>`. Query keys come from `queryKeys` constant; URL state used correctly via `useUrlState`; no `any` types found.)_

<!-- iteration #23: frontend/src/modules/iso-docs -->
_(No blockers. Permission gating verified clean: `IsoDocs.tsx:361-364` derives `isEditor = canEditIsoDocs || isAdmin` from `usePermission(Action.ISO_DOCS_EDIT)` + `usePermission(Action.ADMIN_USERS)` and threads it via prop drilling. `RegistryView.tsx` gates all write affordances at lines 495, 542, 568, 603. Same shape works for InlineCell, Widget, and metadata flows. AlertDialog `preventDefault` pattern is also correctly applied.)_

<!-- iteration #24: frontend/src/modules/playbook -->
_(No blockers. Permission gating verified mostly clean: `Playbook.tsx:194-197` derives `isAdmin = canAdmin || bypassAuth` and `isEditor = canEditPlaybook || isAdmin`. Edit/create/delete affordances are wrapped with `isEditor` checks. AlertDialog patterns correctly use `preventDefault`.)_

<!-- iteration #25: frontend/src/modules/devstack -->
_(No blockers. Permission gating clean: `Catalog.tsx:41` and `EntryDetail.tsx:71` both derive `canManage = usePermission(Action.DEVSTACK_MANAGE)`; write affordances at L102, L194, L107, L279 all gated. All files under 400 LOC — largest is `EntryForm.tsx` at 365.)_

<!-- iteration #26: frontend/src/shared -->
_(No blockers. Layer is well-disciplined: zero `@/modules` or `@/core` imports from shared/; no `any` types in exports; `useUrlState` has solid test coverage. The agent's "Blocker" on `formatCurrency` duplication is just DRY (Minor), and its "dead shadcn components" finding was wrong — `skeleton`, `collapsible`, `sidebar` are all actively used.)_

---

## CALCULATIONS

### WRONG
_(empty)_

### SUSPICIOUS
_(empty)_

### OK
_(empty — record explicit confirmations here so you don't re-audit later)_

---

## Finding template

When appending, use this shape:

```markdown
- **<short title>** — `path/to/file.py:123` [warning] — deferred: scope or refactor cost exceeds this fix-pass; tracked for follow-up.
  - Module: `scorecard / tracker / ...`
  - Repro: `<input → expected vs actual>` (for CALCULATIONS only)
  - Detail: <one paragraph>
  - Fix: <one-line suggestion>
  - Added: 2026-05-14 by audit_tech_debt iteration #4
```
