# Audit Findings

Consolidated output from `audit_tech_debt.md` and `audit_calculations.md`. Each iteration appends new findings; items are then classified as [warning] / [won't do] / [fixed] and bucketed below.

---

## Status (2026-05-15 PM)

**112 fixed · 18 won't do · 133 warning.** Full backend (1844) + frontend (433) + MCP (310) test suites pass on a clean run. Tier 1 + Tier 2 priority pass closed; previously-deferred "disabled governance tool" UX item now landed; and the 3 High-priority items (HP-1, HP-2, HP-3) closed in the same session. The remaining 133 warnings are real but legitimately deferred technical debt — attack them via the boy-scout rule (touch a file, fix its warnings in the same PR), not via dedicated sweeps.

No High priority items currently open. Next audit pass should focus on what's new since 2026-05-15.

---

## Pending — by criticality

Open `[warning]` items grouped by audit severity. Touch the file? Fix the warning in the same PR.

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

112 items closed across the dead-code, test-sweep, Tier 1, Tier 2, and HP passes. Kept for traceability of what was changed and why.

### Blocker (14)

- **HP-1: MCP permission gating is invisible in CI** — `mcp_server/data/base.py:41-46`, all MCP write tools [fixed]
  - Module: `mcp_server`
  - Detail: `FULL_ACCESS = McpUserContext(permissions=["*"])` was the de-facto default for tests that overrode the read session but never the user context. Combined with HP-2, removing a `@mcp_requires` decorator from a write tool would have left CI green AND left no audit-log trace at runtime.
  - Fix: New `restricted_user` pytest fixture (`mcp_server/tests/conftest.py:67`) returns a `McpUserContext` with only `tracker:view`. New `mcp_server/tests/test_write_tool_gating.py` parametrizes over the 13 write tools (9 iso_*, 4 playbook_*) and asserts each raises `ToolError` under that fixture. The day someone deletes a decorator or changes the required permission string, one of these 13 tests fails.
  - Added: 2026-05-14 by audit_tech_debt iteration #15 · promoted to HP: 2026-05-15 · fixed: 2026-05-15 PM

- **HP-2: `mcp_requires` denials looked like successful tool runs** — `mcp_server/auth/permissions.py` [fixed]
  - Module: `mcp_server / auth`
  - Detail: The decorator returned `json.dumps({"error": "..."})` on permission failure. FastMCP wrapped that as a successful tool return, so callers (LLM agents, UIs) could not distinguish "blocked at the gate" from "tool ran and returned a failure structure". An LLM reading the denial message had no signal to stop, and the server emitted no audit event.
  - Fix: Now `raise ToolError(f"Permission denied: requires {permission}")` from `mcp.server.fastmcp.exceptions`, which FastMCP surfaces as a true tool error (the message ends up on the raised exception, not the return). Added a `mcp_permission_denied` structlog warning event with `tool`, `permission`, `user_id`, and `user_email` for the audit trail. All existing tests (`TestMcpRequires`, `TestToolGating`, `test_permission_denied_for_write_tool`) updated to `pytest.raises(ToolError, match=...)`.
  - Added: 2026-05-14 by audit_tech_debt iteration #15 · promoted to HP: 2026-05-15 · fixed: 2026-05-15 PM

- **HP-3: XSS / Slack mrkdwn injection latent in two rendering paths** — `backend/app/modules/playbook/services/publish_service.py:46`, `backend/app/modules/notifications/services/alert_service.py` [fixed]
  - Module: `playbook / publish` + `notifications / alerts`
  - Detail: Two "safe today by accident" rendering paths that the next template-author would have made unsafe without realising.
    - **Jinja** — `_get_jinja_env()` used `autoescape=False`. Only safe because the lone interpolation that handled markdown-pre-rendered HTML went through `{{ content | safe }}` and all other templates happened to only render trusted strings (titles, slugs). Any future `{{ user_supplied_field }}` would have inherited an unsafe default.
    - **AlertService** — `render_template()` stringified context values with no Slack mrkdwn escaping. Currently project/user names come from trusted DB rows, but a Jira-sourced placeholder (e.g. `package_name` from a dependabot alert, or a Jira issue summary) is one template away from a mrkdwn-injection vector that can open hidden bold / italic / link blocks in leadership Slack messages.
  - Fix:
    - `publish_service.py` — flipped to `autoescape=select_autoescape(["html"])`. The single content interpolation (`page.html`) already uses `{{ content | safe }}`, so no double-escape. Full playbook test suite (58) re-runs clean.
    - `alert_service.py` — added module-level `markdown_escape(value)` that escapes `*`, `_`, `` ` ``, `>`, `<`, `|` with a backslash. `render_template` now routes every substituted value through it (missing keys still pass through unchanged so `{missing}` placeholders survive as literal text). New `test_render_template_escapes_mrkdwn_meta` test pins the behaviour against a hostile context.
  - Added: 2026-05-14 by audit_tech_debt iterations #7, #12 · promoted to HP: 2026-05-15 · fixed: 2026-05-15 PM

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

<!-- HP-pass: 2026-05-15 PM -->
_(HP-1/HP-2/HP-3 closed in one session. 1844 backend + 310 MCP + 433 frontend pass clean. Net new tests: +14 (13 write-tool gate tests + 1 mrkdwn-escape regression test). Audit trail for MCP denials now lands in structlog as `mcp_permission_denied`. Playbook Jinja autoescape on; AlertService values are mrkdwn-escaped.)_

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

**Audit complete (2026-05-15).** 39/39 rows reviewed. Scorecard block fully closed on 2026-05-15 PM. Tracker / Capacity / FE-types still open.

**Current state (2026-05-15 PM):**
- **OK: 14** — #1 SPI, #2 CPI, #3 budget_variance(None), #8 Flow, #9 Quality, #11 Satisfaction, #12 Value, #13 Engineering, #15 disabled-governance toggle, #19 SV (not implemented; SPI covers), #22 percent_completed, #23 percent_planned, #29 estimated-flag exclusion, #32 prepopulate_parts (VHUB-124).
- **WRONG: 0** — ~~#37 `formatCurrency`~~ **[fixed]**.
- **SUSPICIOUS, fixed:** ~~#4~~, ~~#5~~, ~~#6~~, ~~#7~~ (3/4 sub-issues; UTC business window deferred), ~~#10~~, ~~#14~~, ~~#16~~ (2/3 sub-issues; cache↔cron race deferred), ~~#17~~ (all 4 sub-issues addressed: status filter dropped → MetricsDB presence is the oracle, weighting exposed both equal+budget side-by-side, normalizers fixed via #14, stale projects flagged in `/scorecard` index).
- **SUSPICIOUS, still open:** #18 CV unimplemented + clamped variance, #20 EAC non-EVM, #21 ETC implicit, #24 burn precision divergence, ~~#25 base_rate=0 ZeroDivisionError~~ **[fixed `c4aaeac9` — currency sub-issue still under #24]**, #26 ECB rate=0 + no historical lookup, ~~#27 invoice MAX(postponed_to)~~ **[fixed `9e8661b9`]**, ~~#28 postponement backdate~~ **[fixed `f084e0de`]**, #30 mood aggregation contaminated by estimated, ~~#31 period rotation idempotency~~ **[fixed `9921bcaf`]**, #33 FA averages partial-reporter drag, #34 user-detail duplicate rows multi-FA, #35 capacity reportable-users 3 leak paths, #36 on-leave too narrow, #38 TS types lying re: Decimal-as-string, #39 chart default-page.

**Module status:**
- **Scorecard (8 SUSPICIOUS):** all addressed (some with deliberate partial scope; see entries for ACCEPT/TO DISCUSS markers).
- **Tracker (11 SUSPICIOUS):** in progress. **All 4 quick wins closed 2026-05-16** (#28, #31, #25, #27). Remaining: #18, #20, #21, #24, #26, #30 (structural / currency family / mood). **Pre-deploy gate:** check prod `SELECT id, date, base_rate FROM reporting_periods WHERE base_rate <= 0` — if any rows exist, migration `071_period_base_rate_gt0` will fail.
- **Capacity (4 SUSPICIOUS):** untouched. Needs product decision on partial-reporter semantics.
- **Frontend (#38):** untouched. TS types lie about Decimal-as-string wire format.

**Commits delivered 2026-05-15 PM (11):**
- `082fe9d0` #37 + #14 (formatCurrency + normalizers)
- `fbfee1ea` #5 + #10 (CFR + risk docstring)
- `7a1e236d` #6 (DORA Elite threshold)
- `1c7f39dd` #17 status filter (later refined)
- `fd553a13` #4 (final-score None)
- `3ef06293` #16 (cache holes)
- `7399aba4` #7 (lead-time business-days + median)
- `4fb88ed5` #17 stale warning UI
- `2efa2c47` #17 budget-weighted dashboard
- `8f8a93b6` #17 drop status filter (MetricsDB presence as oracle)
- `91fa9d78` post-deploy recalc script
- `19607a4a` docs(audit) refresh

**Commits delivered 2026-05-16 (3):**
- `48b4d961` #14 addendum: NULL EVM/Jira columns preserved through deserialization (root cause of brand-new projects scoring 0).
- `988f7cf3` SonarCloud cleanup (dict.fromkeys + remove non-native interactive span in StaleMetricsIcon).
- `scripts/invalidate_score_cache.py` shipped alongside #14 addendum for the post-deploy cache flush.

**Post-deploy 2026-05-16 ops completed:**
- Old admin/operational projects (2018-2020) flipped to `has_scorecard=false`. 18 projects affected, all without MetricsDB, no recalc needed.
- KPI registry export (`iso_docs/services/kpi_export_service.py`) deliberately left reading equal-weighted aggregates only — semantically right for ISO 9001 (quality independent of project size).
- Cache invalidated + `recalc_global_history.py` re-run after #14-addendum deploy: 48 months processed, 48 budgeted.

**Backend 1879 / FE 450 green. All commits pushed to `dev` + `main` 2026-05-16.**

**Multi-step families still open:**
- **Currency end-to-end** (#18 / #24 / #25 / #26 / #38): backend cost paths still implicit EUR + no historical FX lookup. FE display (#37) already correct.
- **Capacity completeness** (#33 / #34 / #35 / #36): single product decision before code.
- **EVM modernization** (#18 / #20 / #21): CV/EAC/ETC missing or non-standard.

**Deliberately deferred sub-issues** (revisit if real signal):
- #7 UTC business window for lead-time (bias is proportional across single-TZ teams).
- #16 race condition between cache and cron (bounded by 1h TTL, no incident).
- #17 equal-weighting policy: superseded by exposing both equal+budget side by side.
- #17 stale-snapshot leakage: surfaced in UI instead of backend filtering.

---

### WRONG

- **[fixed 2026-05-15] `formatCurrency` silently shows EUR for every non-legacy currency code** — `frontend/src/shared/utils/evmCalculations.ts:25` (base), `frontend/src/modules/tracker/utils/constants.ts:4` (wrapper). Resolution: `LEGACY_CURRENCY_MAP` keeps backward compat for `euro`/`dollar` callsites; any other input is uppercased and passed directly to `Intl.NumberFormat`, with `ISO_LOCALE_MAP` providing locales for EUR/USD/GBP/CHF/JPY/AUD/CAD and en-US as default fallback. 9 tests added in `frontend/src/shared/utils/__tests__/evmCalculations.test.ts`.
  - Module: `tracker` (worst affected, but cross-cutting on every invoice + EVM screen)
  - Repro: backend normalizes `invoice.currency` to ISO-4217 codes (`admin_invoices.py:147-150`: `"USD"`, `"EUR"`, `"GBP"`, `upper(other)`). FE `CURRENCY_MAP` has ONLY `"euro"` / `"dollar"` keys. Any ISO code falls through to `?? CURRENCY_MAP.euro` (de-DE locale, € symbol). So:
    - `formatCurrency(100, "USD", 2)` → `"100,00 €"` (WRONG — should be `"$100.00"`).
    - `formatCurrency(100, "GBP", 2)` → `"100,00 €"` (WRONG — should be `"£100.00"`).
    - `formatCurrency(100, "EUR", 2)` → `"100,00 €"` (right symbol by accident, wrong locale logic).
  - Affected call sites: `InvoicesCard.tsx:75`, `AdminInvoices.tsx:91`, `invoice-shared.tsx:184/270/504`, `InvoiceDetail.tsx:144` — every place that renders invoice amounts.
  - This is the user-visible part of the currency-handling family (cross-ref #18, #24, #25, #26). The backend correctly stores and serves the currency code; the FE just doesn't know what to do with it. Easy to fix and high impact.
  - Other latent: `null`/`undefined` not guarded (`Intl.NumberFormat.format(undefined)` → `"NaN €"`); string input from Pydantic Decimal coerces in Intl but breaks upstream arithmetic; zero-decimal currencies (JPY) get forced two-decimal format.
  - Tests today: **none**. No test imports `formatCurrency` anywhere. Two helpers, zero coverage on either.
  - Suggested:
    - `formatCurrency(100, "USD", 2) → "$100.00"` (would fail today).
    - `formatCurrency(100, "GBP", 2) → "£100.00"` (would fail today).
    - `formatCurrency(100, "euro", 2) → "100,00 €"` (legacy passthrough still works).
    - `formatCurrency(null, "USD") → ""` or `"—"` (currently `"NaN €"`).
    - `formatCurrency(-50, "USD", 2) → "-$50.00"`.
  - Fix: make `CURRENCY_MAP` accept both legacy (`euro`/`dollar`) and ISO-4217 keys (case-insensitive). For ISO codes, pass the code directly to `Intl.NumberFormat(undefined, { style: 'currency', currency: code, ... })` and let the runtime pick the locale. Drop the hardcoded `de-DE` / `en-US` mapping for unknown codes. Adds full ECB-supported currency coverage in one change.
  - Added: 2026-05-15 (calc-audit row #37)


### SUSPICIOUS

- **[fixed 2026-05-15] Final score returns 0 (not None) when all dimensions are None** — `backend/app/modules/scorecard/services/calculators/final_score.py:99-101`. Resolution: `FinalScore.score` loosened to `int | None`; `calculate_all` now returns `score=None` with all weights at 0 when no dimension has data. Frontend `FinalScore` type updated to match; `ScoreCard.tsx` renders `—` when score is null. Test `test_no_data_final_score` updated to assert None; new `test_weights_all_zero_when_no_data` pins the contract. **Production impact:** brand-new / no-metric projects now render as "—" instead of a flat 0 in dashboards.
  - Module: `scorecard`
  - Repro: `FinalScoreCalculator(cfg).calculate_all(IndicatorsCreate())` → `FinalScore(score=0, ...)` — expected `score=None` per CLAUDE rule "missing indicators are excluded, not penalized". The existing test `tests/test_calculators.py::TestFinalScoreCalculator::test_no_data_final_score` actively pins the wrong behaviour (`assert result.score == 0`).
  - Why this matters: a brand-new project (no metrics yet) appears in dashboards as a flat 0, indistinguishable from a project that genuinely scored 0 across all dimensions. Per-dimension calculators correctly return None in this case; only the final aggregator diverges.
  - Schema constraint: `FinalScore.score` is typed `int` — fixing requires loosening to `int | None`, then audit FE renderers (likely `formatCellValue` already handles null → "—").
  - Fix: when `available` set is empty, return `score=None` and zero `weights_applied`. Update the existing test to assert None. Run `rg "score" frontend/src/modules/scorecard/` to find any `.toFixed()` / arithmetic on `finalScore.score` that needs a null guard.
  - Added: 2026-05-15 (calc-audit row #4)

- **[fixed 2026-05-15] DORA Change Failure Rate — upper bound contract not enforced** — `backend/app/modules/scorecard/services/collectors/github/change_failure_rate.py:120`, schema `backend/app/modules/scorecard/models/indicators.py:69`. Resolution: added `le=100` to `IndicatorsCreate.change_failure_rate`, defensive `min(cfr, 100.0)` clamp at the collector, and synchronized the collector docstring with the actual classifier thresholds (Elite 0-5/High 5-10/Medium 10-15/Low >15). 4 contract tests in `test_github_change_failure_rate.py`.
  - Module: `scorecard`
  - Background: the production-incident commit `7774abb2` widened the DB column from `NUMERIC(5,4)` to `NUMERIC(5,2)`. Root cause was the column being too narrow to store a legitimate 41.7% CFR. The widening fixed the immediate crash, but the *contract* that CFR is `0 ≤ x ≤ 100` is still not enforced anywhere: no `le=100` on Pydantic `IndicatorsCreate.change_failure_rate`, no defensive clamp in the collector, and `NUMERIC(5,2)` silently absorbs any 100 < x < 1000 anomaly without flagging.
  - Repro for the silent-absorption case (hypothetical, not currently reachable from production code): future collector change that uses a different denominator → emits `cfr=150.0` → Pydantic accepts (only `ge=0`) → DB stores 150.00 → classifier returns "Low", no alert.
  - Edge case missed: documentation drift — collector docstring at `change_failure_rate.py:33-37` claims bands "Elite 0-15%, High 16-30%, Medium 31-45%, Low >45%" but the actual `_classify_change_failure_rate` in `dora.py:184-191` uses standard DORA thresholds (5/10/15). Confusing for future readers, runtime unaffected.
  - Tests today: thresholds at 5/10/15/16 covered, no test pins 100% boundary, no test pins NUMERIC(5,2) round-trip for realistic values like 41.7.
  - Suggested: `test_cfr_100_percent_classifies_low`, `test_cfr_collector_returns_100_when_every_pair_is_hotfix`, `test_metrics_db_accepts_realistic_cfr_41_7` (regression for the original incident).
  - Fix: add `le=100` to `IndicatorsCreate.change_failure_rate` and `min(cfr, 100.0)` defensive clamp at `change_failure_rate.py:120`. Update the collector docstring to match the actual DORA thresholds in `dora.py`.
  - Added: 2026-05-15 (calc-audit row #5)

- **[fixed 2026-05-15] DORA deployment frequency — Elite threshold inconsistent with its own docstring** — `backend/app/modules/scorecard/services/calculators/dora.py:141-156`. Resolution: classifier tightened to `> 1.0` to match the docstring and DORA literature ("multiple deploys per day"). Teams deploying exactly once per day now classify as High (was Elite). Test in `test_dora_calculator.py::test_deployment_frequency_thresholds` updated to assert this boundary explicitly. **Production note:** any project sitting at exactly 1.0 deploys/day will drop one tier on the next calculation.
  - Module: `scorecard`
  - Repro: `IndicatorsCreate(deployment_frequency=1.0)` → classifier returns Elite (score 100). The classifier docstring at `dora.py:41` says "Elite: Multiple deploys per day" (i.e. >1), but the threshold uses `>= 1.0`. A team deploying exactly once per day gets Elite when both the in-file documentation and the DORA literature say High.
  - Either tighten classifier to `> 1.0` and update tests, or update the docstring/comments to acknowledge the threshold is "≥ 1.0". Small thing but it muddies the meaning of the tier.
  - Cosmetic finding (same agent): the collector returns key `release_count_90d` even when running in punctual mode over an arbitrary window (`deployment_frequency.py`). Misleading name; consider `release_count` + a separate `window_days` field.
  - Tests today: thresholds at 1.0 / 0.143 / 0.034 / 0.01 covered but boundary `>1.0` and exact-1/7 / exact-1/30 not pinned.
  - Suggested: `test_elite_requires_multiple_per_day`, `test_punctual_uses_period_window` (asserts key name doesn't lie), `test_collector_excludes_zero_division` (1-day window with 1 release → 1.0/day, no div-by-zero).
  - Fix: either tighten the classifier or update docs; rename or split the collector return key. One-line each.
  - Added: 2026-05-15 (calc-audit row #6)

- **[mostly fixed 2026-05-15] DORA "Lead Time" — unit mismatch + mean instead of median + UTC-only business window + mislabeled metric** [UTC sub-issue ACCEPTED 2026-05-15: small bias, proportional across teams, refactor disproportionate to current single-TZ team] — calculator `backend/app/modules/scorecard/services/calculators/dora.py:158-174`, collector `backend/app/modules/scorecard/services/collectors/jira/lead_time.py:91` (and `_calculate_issue_lead_time` at :72), business-time helper `backend/app/modules/scorecard/services/collectors/jira/utils.py:98`. Resolution: (1) **Unit mismatch closed** — `_classify_lead_time` thresholds re-expressed in business days (Elite <1 business hour = 1/9 BD, High <1 BD, Medium <5 BD, Low ≥5 BD). Both the calculator and collector now share the same unit, and the docstrings call out the unit explicitly. (2) **Mean → median** — `collect_lead_time` aggregates with `statistics.median` so a single 30-day outlier no longer flips the team's tier (new test `test_collect_lead_time_median_resists_outlier` pins this). (3) **Label honesty** — docstrings in both files now state explicitly: "this is NOT DORA Lead Time for Changes (commit→deploy); it is Jira cycle time (in-progress→resolved)." (4) **UTC-only business window** deliberately deferred — fixing properly needs a per-team TZ setting and a refactor of `business_days_diff`; the impact on Madrid-based teams is small (the 2h offset systematically under-counts ~2/9 ≈ 22% of business hours, but proportionally across all teams). Will revisit when the company spans more time zones. **Production impact:** projects with outlier tickets will see lead_time_days drop on next capture (median is lower than mean for skewed distributions). Borderline cases at 5-7 business days may shift one tier (e.g. 6 BD was Medium under calendar-day thresholds → still Medium, no change; 5 BD was Medium → now Low).
  - Module: `scorecard`
  - Stacked findings (one row = several issues, all in the same code path):
    1. **Unit mismatch (most important).** Collector emits *business days* (1 unit = 9 working hours, 09:00–18:00 UTC, Mon–Fri). DB column is `Numeric(10,2)` named `lead_time_days`. Classifier compares against calendar-day thresholds (Elite `<1/24`, High `<1`, Medium `<7`, Low `≥7`). So 7 business days ≈ 9.8 calendar days; a 1-business-day issue is `1.0` and the classifier reads it as "1 calendar day → High". The unit is silently inconsistent across collector → DB → classifier.
    2. **Mean, not median.** Collector aggregates with `sum/len` (lead_time.py:131). DORA literature and any robust statistic on cycle time uses median to tame outliers. Repro: 9 issues × 1 day + 1 × 90 days → mean 9.9 (classified Low), median 1 (High). The current "score" is the kind that a single neglected ticket can flip.
    3. **UTC-only business window.** `business_days_diff` uses 09:00–18:00 UTC. Madrid 09:00 = 07:00 UTC → counted as "before hours". Repro: in-progress `2024-06-03T09:00:00+02:00`, resolved `2024-06-03T18:00:00+02:00` → ~0.78 business days. Madrid teams systematically score worse than their work day actually was.
    4. **Mislabeled metric.** DORA "Lead Time for Changes" = commit → production deploy. This implementation measures Jira issue cycle time (first-in-progress → resolved). Tier comparisons are nonsensical against the DORA spec; there is no commit-to-deploy correlation in the pipeline.
    5. **No upper cap / no tz-naive guard / re-opened issues counted only on first cycle.** Stale-issue tail dominates the mean. tz-naive datetimes sneaking in would raise `TypeError`.
  - Tests today: collector path covered (JQL shape, In-Progress changelog, business-days math, weekend skip). Calculator thresholds covered. None of the above semantic issues are pinned.
  - Suggested: `test_collect_lead_time_outlier_dominates_mean`, `test_collect_lead_time_with_local_timezone`, `test_collect_lead_time_negative_or_zero_excluded`.
  - Fix (layered, pick the smallest one first):
    - Minimum: rename `lead_time_days` → `lead_time_business_days` everywhere, and either re-express classifier thresholds in business-day units (1h ≈ 1/9, 1 day = 1, 1 week = 5) OR convert at the boundary. Stop the silent unit-confusion.
    - Better: switch aggregation from `sum/len` to `statistics.median(lead_times)`.
    - Long-term: rename the metric on screen + in docs from "DORA Lead Time" to "Jira cycle time" until a real commit→deploy collector exists.
  - Added: 2026-05-15 (calc-audit row #7)

- **[fixed 2026-05-15] Risk calculator docstring drift on PR-review target** — `backend/app/modules/scorecard/services/calculators/risk_calculator.py:12`. Resolution: docstring updated from "target 2% of total PRs" to "target ~10% of total PRs (see config `target_pr_no_review_ratio`)".
  - Module: `scorecard`
  - Repro: docstring claims "target 2% of total PRs" but seeded default in `tests/conftest.py:95` is 10 (10%). Functionally the calculator reads the value from config so the math is right; the doc is just stale and misleads anyone debugging Risk scores.
  - Edge cases otherwise handled: high_vulns=0 → 1.0; high_vulns≥target → floor 0; target=0 strict mode (1.0 if 0 else 0.0); prs_without_review None / total_prs=0 → PR component excluded; weights 0.50/0.50 sum 1.00; Pydantic `ge=0` blocks negatives; CLAUDE alerts-toggle rule honored (no `has_dependabot_alerts` references anywhere in `services/calculators/`).
  - Tests today: TestRiskCalculator covers perfect, gradual vuln penalty, no-data, single-component, zero-total-prs. Missing: `target=0` zero-tolerance branch, `pr_target=0` strict branch, `high_vulns >> target` floor-at-0.
  - Suggested: `test_strict_zero_vuln_tolerance`, `test_vulns_far_above_target_floors_at_zero`, `test_pr_target_zero_strict`.
  - Fix: update docstring to match seeded default ("target ~10% of total PRs (see config `target_pr_no_review_ratio`)"). Trivial doc edit.
  - Added: 2026-05-15 (calc-audit row #10)

- **[fixed 2026-05-15 + 2026-05-16] Indicator normalizers violate the "missing excluded, not neutralized" rule in 5 places** — `backend/app/modules/scorecard/services/normalizers/indicators.py`. **2026-05-16 addendum:** post-deploy diagnosis revealed the same anti-pattern one layer up in `metrics/schemas.py::_build_evm_data` and `_build_jira_defects` — NULL DB columns were silently coerced to 0 during MetricsDB→Pydantic hydration. This made SPI=0 (instead of None) for projects with budget but no progress capture (e.g. brand-new projects, projects without EVM tracking). Now `EVMData.percent_completed/percent_planned/cost_to_date` and `JiraDefectMetrics.bugs_total/tasks_completed/escaped_defects` are `int|None`/`float|None`; `_normalize_spi/_cpi` and `_calculate_defect_density/_calculate_escaped_rate` add explicit None guards. 9 regression tests in `test_normalizers_missing_excluded.py` (TestEvmNoneSemantics, TestDefectAndEscapedAllowNullInputs). **Resolution (original 2026-05-15):** all 6 paths rewritten. `_normalize_test_maturity` + `_normalize_pm_satisfaction` now follow the `_normalize_client_survey` weighted-average pattern (skip None / `ComplaintStatus.NA`, redistribute remaining weights, return None when nothing remains). `_calculate_defect_density` and `_calculate_escaped_rate` return None when `tasks_completed <= 0` instead of 0.0. `_get_mttr` returns None when `incidents_count == 0` instead of 0.0. `_normalize_okr_impact` drops the `NEUTRAL_VALUE` fallback. `NEUTRAL_VALUE` import removed from the file. 14 regression tests in `backend/tests/test_normalizers_missing_excluded.py` + `test_mttr.py::test_no_incidents_returns_none` updated. **Expected production impact:** projects with partial data will see scores move on the next capture (previously inflated toward ~50%).
  - Module: `scorecard`
  - The CLAUDE rule promises that a `None` indicator is dropped from the weighted average. The base helper `_weighted_average` enforces this faithfully, and `_normalize_client_survey` (indicators.py:269) is a clean reference implementation: it drops None sub-fields, redistributes weights, returns None when nothing remains. The *other* composite normalizers diverge — they silently substitute neutral values, so a project with zero data scores ~50% instead of being marked "no data".
  - Specific violators:
    1. `_normalize_test_maturity` (indicators.py:197) — each missing sub-rating (e2e/unit/accessibility/security/frontend) substitutes `NEUTRAL_VALUE` (0.5). Repro: `TestMaturity(e2e=None, unit=None, accessibility=None, security=None, frontend=None)` → expected None, actual ≈0.5.
    2. `_normalize_pm_satisfaction` (indicators.py:252) — `default_complaint_score=0.75` for `ComplaintStatus.NA` and `NEUTRAL_VALUE=0.5` for missing `overall_estimation`. Repro: `PMSatisfaction()` with all defaults → expected None, actual 0.65.
    3. `_calculate_defect_density` (indicators.py:134) — collapses "tasks_completed ≤ 0" to 0.0 (= "perfect"), making zero-tracking identical to perfect-quality. Repro: `JiraDefectMetrics(bugs_total=3, tasks_completed=0)` → expected None (no denominator), actual 0.0.
    4. `_calculate_escaped_rate` (indicators.py:144) — same fallback as defect_density.
    5. `_get_mttr` (indicators.py:152) — returns 0.0 when `incidents_count==0`. Documented as intentional ("no incidents = perfect MTTR"), but inconsistent with the rest of the file and indistinguishable from "incidents not tracked". Projects without incident tracking are flattered.
    6. `_normalize_okr_impact` (indicators.py:239) — `NEUTRAL_VALUE` fallback for unknown enum (cross-referenced from row #12). Currently unreachable thanks to Pydantic, but the dead branch encodes the wrong policy.
  - Why this matters: these violations flatten the score upward whenever data is missing. A new project with no Jira → defect_density 0 → Quality dim looks better than reality. A team without test_maturity self-assessment → Engineering dim sits near 50 instead of being marked "no data". The "missing excluded" rule is the load-bearing fairness invariant of the whole scoring system; broken in 5 places.
  - Tests: base-layer helpers (`normalize_lower_is_better`, `normalize_governance_compliance`, etc.) are thoroughly tested. The `_normalize_*` / `_calculate_*` private methods on the composite normalizers have no direct unit coverage. Integration tests cover perfect/poor paths only.
  - Suggested: `test_normalize_test_maturity_all_none_returns_none`, `test_normalize_pm_satisfaction_all_defaults_returns_none`, `test_calculate_defect_density_zero_tasks_returns_none`.
  - Fix: rewrite `_normalize_test_maturity` and `_normalize_pm_satisfaction` after the `_normalize_client_survey` pattern (drop None / NA fields, redistribute weights, return None when `weight_sum == 0`). Flip `_calculate_defect_density`, `_calculate_escaped_rate`, `_get_mttr`, and `_normalize_okr_impact` from silent neutral fallbacks to None so the calculator's `_weighted_average` can exclude them. Each fix is localized; tests update accordingly.
  - Added: 2026-05-15 (calc-audit row #14)

- **[partially fixed 2026-05-15] Score cache: two real invalidation holes + race condition on concurrent writers** — `backend/app/modules/scorecard/services/score_cache.py:35`. Resolution: **Hole 1** — DELETE project now takes `OptionalScoreCache` and calls `cache.invalidate(str(project_id))` after `db.delete(project)`. **Hole 2** — `api/capture.py` no longer write-throughs after `flush()`. It invalidates instead, so a request rollback can never leave Redis ahead of DB (cache trails the DB, never leads it). The next read recomputes from DB and lazy-populates. **Race condition on concurrent writers (cron + manual capture) [ACCEPTED 2026-05-15]:** decision is to leave it as-is. Bounded by 1h TTL, no incident observed; locks / version stamps disproportionate to the risk.
  - Module: `scorecard`
  - Hole 1 — **Project deletion does not invalidate** (`backend/app/core/api/projects_v2.py:351`). DELETE removes the project + metrics but leaves the Redis key in place until the 1h TTL expires. Practical impact: minor (the project is gone so the API returns 404 before consulting cache), but the key takes memory and leaks if UUIDs are ever recycled (e.g., test fixtures restoring from a backup).
  - Hole 2 — **Write-through cache.set runs before request commit**. The capture-period endpoint at `backend/app/modules/scorecard/api/capture.py:289` calls `cache.set(...)` after `db.flush()` but before the FastAPI request commit. If the transaction later rolls back, Redis holds scores that never persisted to DB → stale-positive cache for up to 1h. Same pattern around `config.py:130` `invalidate_all` — clears cache, then commit may fail; until next write, cache will re-fill from the OLD DB row.
  - TOCTOU window — concurrent writers (e.g. cron `monthly_scorecard_capture` running at the same time an API capture is triggered for the same project) can interleave invalidate/set. No CAS / version stamp / Lua. Window is short but real; eventually consistent within 1h TTL.
  - None-guard pattern (`if cache:`) is consistently applied at every call site — no violators.
  - Tests today: `tests/test_score_cache.py` covers unit-level get/mget/set/invalidate including silent degradation on Redis errors. No test for the deletion hole, the rollback hole, or the concurrent-writer race.
  - Suggested: `test_delete_project_invalidates_cache`, `test_capture_rollback_does_not_leave_stale_set`, `test_concurrent_invalidate_set_last_writer` (documents TOCTOU as bounded by TTL).
  - Fix:
    - In `delete_project` (`projects_v2.py:~352`): `if cache: await cache.invalidate(str(project_id))` before the response.
    - In `capture.py:289` (and the other write-through site): prefer `cache.invalidate(project_id)` over `cache.set(...)` so a later rollback can't leave Redis ahead of DB. Read-through will re-populate on the next request.
  - Added: 2026-05-15 (calc-audit row #16)

- **[fixed 2026-05-15] Global metrics aggregation includes archived/cancelled projects + equal-weighted** — `backend/app/modules/scorecard/services/global_metrics_service.py:75` (`calculate_and_store`), :134 (`_average_indicators`), :163 (`_average_scores`). Resolution: (1) **Membership oracle:** dropped the status filter entirely. A project belongs to month M's aggregate iff it has a `MetricsDB` row for M. The cron (`monthly_scorecard_capture.py`) already filters `status == 'live'` upstream, so FINISHED/PROPOSAL projects don't grow new rows; their historical rows correctly reflect the months when they were active. This handles the planned-vs-actual end_date drift naturally. `strategic_impact.strip().lower()` for label sanity. (2) Sub-issue #3 (the #14 normalizer cluster) fixed independently. (3) **Sub-issue #2 (equal weighting):** now expose BOTH equal-weighted and budget-weighted aggregates side by side. Migration `070_global_by_budget.py` adds 9 `_by_budget` columns + `budget_weighted_project_count`. `BudgetWeightedScores` schema in `models/global_metrics.py`, `_average_scores_by_budget` in service. Projects without budget are excluded from the budget aggregate (count reported). Frontend renders two `GlobalScoreCard`s (equal + budget) and the route moved from `/admin/global-scores` to `/scorecard/global` — accessible to all users; Calculate/Recalculate buttons remain admin-gated. (4) **Sub-issue #4 (stale-snapshot leakage):** surfaced in UI via warning icon on stale project cards in `/scorecard` index (commit `4fb88ed5`).
  - Module: `scorecard`
  - What it does well: None-handling is correct — `_average_indicators` and `_average_scores` filter `is not None` before averaging; empty period yields `(value=None, count=0)`; idempotent upsert by `(period_year, period_month)`. The None-exclusion contract holds at the portfolio layer.
  - Issues:
    1. **No project-status filter.** Line 97-102 joins `MetricsDB` for the period only. Archived / cancelled / on-hold / draft projects with a stale CUMULATIVE row in the period get folded into the portfolio average and into `project_count`. Repro: cancel a project today; the same project shows up in next month's global average with its last-known score. The metric is supposed to reflect the portfolio "right now", not the portfolio "ever existed".
    2. **Equal weighting** — a 1M€ project and a 10k€ side experiment count the same. Not a bug per se, but it makes the headline number unreliable as a portfolio-health signal. Document the choice or weight by budget/headcount.
    3. **Cross-ref to row #14** — the per-project pipeline produces false 0.0 / 0.5 scores when normalizers like test_maturity / pm_satisfaction / defect_density swallow missing data with a neutral fallback. The global aggregator treats those zeros as real, so the global score is also polluted. Fixing #14 fixes this transitively.
    4. **Stale-snapshot leakage** — if a project stops capturing (worker disabled or repo gone), its CUMULATIVE row from the last successful month persists into later period aggregations only if MetricsDB rows are re-created with new period anchors; otherwise the project silently disappears from later months and `project_count` shrinks without explanation. Visible in `available_months` history; needs to be surfaced or filtered explicitly.
    5. **Minor** — `metrics_db.strategic_impact.lower()` (line 122) doesn't `.strip()`, so a label `"High "` falls to None silently.
  - Tests today: 17 tests cover indicator-mean / score-mean / upsert / API / batch / history. Missing: project-status filtering, "0 is real" vs None semantics, count decoupled from project_count integration test.
  - Suggested:
    - `test_excludes_archived_projects` (insert 2 live + 1 archived, expect `project_count == 2`).
    - `test_zero_score_is_not_excluded` (pin "score=0.0 is a real measurement, included in mean").
    - `test_count_decoupled_from_project_count` (3 projects, only 1 reports cpi → `project_count=3` but `cpi_count=1`).
  - Fix: at line 97, JOIN to `ProjectDB` and filter `ProjectDB.status.in_(...)` based on product call. Decide weighting policy explicitly and document. Strip-and-lower for strategic_impact label.
  - Added: 2026-05-15 (calc-audit row #17)

- **EVM Cost Variance (CV = EV − AC) not implemented; only CPI + clamped overrun** — `backend/app/modules/scorecard/services/normalizers/indicators.py:85` (EV), `:79` (CPI), and `backend/app/modules/scorecard/services/normalizers/base.py:125-148` (budget_variance overrun).
  - Module: `tracker` (consumer) + `scorecard` (producer)
  - What exists today: EV is computed (`budget_total × percent_completed`) backend and frontend (`evmCalculations.ts:14`); CPI is computed (`EV/AC`); `budget_variance` is `max(0, AC/budget − 1)` — i.e. clamped to ≥0, sign discarded.
  - What is missing: CV = EV − AC. No backend field, no API exposure, no frontend rendering. EVMSection shows EV and Cost-to-Date as separate cells but never their difference.
  - Why the clamp is a problem: `budget_variance` lumps "on budget" and "under budget" together — a project with EV=120k, AC=100k (CV=+20k under) reports the same `budget_variance=0.0` as a project running exactly on budget. The signal that you're *ahead* on cost is lost. Stakeholders asking "how much money over/under?" get a ratio (CPI) or a clamped overrun, never the absolute number.
  - Currency: `EVMData` carries no currency tag. `budget_total` (project currency) and `cost_to_date` (aggregated tracker reports, possibly mixed-currency via rates) are subtracted/divided as raw floats. No FX call in the normalizer path. If the project currency differs from any contributor's rate currency, EV − AC and AC/PV are arithmetically wrong. Document the single-currency assumption or call `exchange_rate_service` at the boundary.
  - Decimal precision: `MetricsDB.cost_to_date` / `budget_total` are Decimal in DB but float in `EVMData` (`api_models.py:6`). Precision lost on the way into the scorecard snapshot.
  - Tests today: no test asserts `CV = EV − AC` anywhere. `weight_cost_variance` is a config key (a scoring weight) — not the same thing.
  - Suggested (if CV is added):
    - `test_cost_variance_basic`: BAC=100k, %completed=0.5, AC=40k → CV=+10k.
    - `test_cost_variance_negative_preserved`: BAC=100k, %completed=0.5, AC=70k → CV=−20k (sign kept).
    - `test_cost_variance_missing_inputs_returns_none`: cost_to_date=None or percent_completed=None → CV=None.
  - Fix: add `cv = ev − cost_to_date` in `evmCalculations.ts:14-17` and surface as a third row in `EVMSection.tsx` with sign-preserving `formatCurrency`. Backend: expose `cost_variance` in `EVMData` returning None when any input is None and preserving sign. Decide whether the clamped `budget_variance` should remain for scoring or be replaced by signed CV.
  - Added: 2026-05-15 (calc-audit row #18)

- **EAC (Estimate at Completion) uses a non-standard time-based forecast, ignoring CPI/BAC/EV** — `frontend/src/modules/tracker/components/BurnDashboard.tsx:82` (`forecastFinal`), with helpers `weightedMonthlyAvg` and `buildForecastPoints` in the same file.
  - Module: `tracker`
  - Formula used: `forecastFinal = totalBurn + (weightedMonthlyAvg × remainingMonths)`. `weightedMonthlyAvg` weights the last 3 months 3/2/1 (older months weight 1). `remainingMonths` is calendar months between the last burn period and `project_end_date`. This is effectively `AC + ETC` where ETC is a time-driven extrapolation of recent burn — *not* the standard EVM `EAC = BAC/CPI` nor `EAC = AC + (BAC − EV)`. CPI, BAC, and percent_completed are not consulted.
  - API exposure: none. Computed client-side only inside `useChartData`. Backend exposes `burn_percentage` but no EAC/forecast field.
  - Edge cases handled: missing `project_end_date` skips forecast; `remainingMonths ≤ 0` (already past end) returns `totalBurn`; empty/single-period inputs handled.
  - Edge cases missed / minor:
    - Day-of-month is ignored — period dated `2026-01-31` and end date `2026-02-01` yields `remainingMonths=1`, inflating the forecast by a full month of burn.
    - Months with zero spend (paused / holidays) drag `weightedMonthlyAvg` down → optimistic forecast. A single anomalous high-spend month near the end (weight 3) skews the projection dramatically.
    - Chart caps at 24 forecast points but `forecastFinal` is still computed for the full `remainingMonths` — chart and KPI silently disagree past 24 months.
    - No comparison against BAC (budget), so no "projected overrun" alert in the data layer.
    - Currency: assumes all `period.total` values are already in project currency; no FX guard (same family of finding as row #18).
  - Tests today: **none**. No test imports `BurnDashboard`, `useChartData`, `weightedMonthlyAvg`, `buildForecastPoints`, or `evmCalculations`. The entire forecast path is uncovered.
  - Suggested:
    - `weightedMonthlyAvg`: `[100,100,100,100]` → 100; `[0,0,0,300]` → ~150 (weight-3 dominates); `[]` → 0; `[50]` → 50.
    - `useChartData.forecastFinal`: 3 months at €1k each, end date +2 months → forecastFinal ≈ 5000; end date in past → forecastFinal === totalBurn.
    - `useChartData` truncation: end date +30 months → cumulative array has 24 forecast points but `forecastFinal` reflects all 30 months (document the asymmetry).
  - Fix: rename `forecastFinal` → `projectedFinalCost` and document the formula `AC + (weighted_recent_burn × remaining_calendar_months)`. Add a sibling EVM-based EAC (`budget_total / cpi` when `cpi > 0`) so users can compare time-trend vs cost-performance projections; flag a divergence > 15%.
  - Added: 2026-05-15 (calc-audit row #20)

- **ETC (Estimate to Complete) not exposed separately; only implicit inside EAC** — sister finding to row #20. `frontend/src/modules/tracker/components/BurnDashboard.tsx:82`.
  - Module: `tracker`
  - Implicit formula: `ETC = weightedMonthlyAvg × remainingMonths` (the "remaining work cost" term of the EAC forecast from #20). Stakeholders only see the EAC ("Forecast Final"), never the remaining-cost number on its own.
  - Same non-EVM design as row #20 (time-trend, ignores BAC/EV/CPI). Additional ETC-specific edge cases not handled:
    - `weightedMonthlyAvg` can go negative when a period contains a refund/reversal (PeriodCostBreakdown.total is signed) → forecast < totalBurn, no clamp.
    - **Gap-in-reporting inflation**: `remainingMonths` is calendar months between the *last reported period* and `projectEndDate`. If a team stops reporting for 3 months and reports again right before the end date, those gap months get treated as future months and multiplied by `weightedMonthlyAvg` → double-counted overshoot.
    - **NaN leak guard**: `new Date(endDate + 'T00:00:00')` on a malformed date yields NaN; `NaN > 0` is false so it falls through silently. Defensible (forecastFinal stays null) but not surfaced.
    - Single zero-cost period (paused/holiday) → weightedAvg=0 → forecast = totalBurn → masks under-reporting.
  - Tests today: none (same as #20).
  - Suggested: `weightedMonthlyAvg([100,200,300]) → 233.33`, `weightedMonthlyAvg([]) → 0`, `buildForecastPoints(remainingMonths=3, totalBurn=1000, weightedAvg=200)` → forecastFinal=1600 / 3 points, refund-period test, malformed end-date test.
  - Fix: same as #20 — expose backend ETC alongside EAC using EVM-standard inputs (`max(0, BAC − EV)` and `(BAC − EV) / max(CPI, ε)`) so stakeholders see "Remaining" as a separate KPI and the time-trend forecast is one method among several. Also: add a "last reporting gap" warning when there's a gap > 1 month between the last reported period and today.
  - Added: 2026-05-15 (calc-audit row #21)

- **Burn percentage — single-vs-batch precision divergence + null-when-zero conflation + currency gap** — `backend/app/modules/tracker/services/aggregation_service.py:129` (single) and `:199` (batch).
  - Module: `tracker`
  - Formula: `burn_percentage = (Σ valid report-part cost + Σ non-staff cost) / project.budget × 100`, where `valid` excludes `estimated=true` parts and `percentage<=0` parts (per CLAUDE rule). Returns null when `budget` is falsy.
  - Issues:
    1. **Precision divergence**: line 128 (single-project endpoint) does NOT round `total_cost` before dividing; line 198-199 (batch endpoint) rounds to 2dp before dividing. Same project queried via both endpoints returns slightly different `burn_percentage` (existing tests paper over with `abs=0.01`). Repro: a project whose total_cost is `7822.06` → single endpoint divides `7822.06 / budget × 100`, batch divides `7822.06 → 7822.06 → same` (in this case OK), but with longer decimals the rounding diverges. Pick one precision policy and apply consistently.
    2. **budget=0 vs budget=None conflation**: `if budget else None` (truthy check) treats `Decimal("0")` and `None` identically. ProjectDB.budget has `ge=0` so 0 is a valid stored value. Currently masquerades as the "null when zero" rule but actually short-circuits on falsy. Not pinned by any test — a future refactor that switches to `if budget is None` would change behavior for legitimate-zero projects.
    3. **Currency mismatch** (same family as #18): `project.budget` is in `project.currency`; `report_part.cost` and `non_staff_cost.cost` are stored as raw numerics with no currency tag. They're silently assumed to share project.currency. No `exchange_rate_service` call. If a user's `rate` is in a different currency from `project.currency`, burn% is arithmetically meaningless.
    4. **Non-staff costs never excluded as estimated**: there's no `estimated` flag on `non_staff_cost` (project-level, not report-level), so they enter every cumulative regardless of whether report-level data is estimated. Documented? Probably intentional; flagging for clarity.
    5. Uncapped overrun: cost > budget → e.g. 150%. Design choice; not a bug. Worth pinning in a test so it doesn't accidentally regress to a cap.
  - Tests today: happy path + estimated-exclusion + null-budget + empty-project covered. Missing:
    - `test_cost_summary_budget_zero` (budget=Decimal("0") with cost>0 → null, not ZeroDivisionError; pin truthy behavior).
    - `test_cost_summary_overrun` (cost > budget → >100, uncapped, exact value e.g. 150.0).
    - `test_cost_summary_zero_cost_positive_budget` (budget=50000, no report parts → 0.0, NOT null).
    - `test_batch_vs_single_consistency` (same project both endpoints → burn% matches; would fail today due to rounding asymmetry).
  - Fix: (a) align rounding policy at line 128 with line 198; (b) optionally tighten the null guard to `if budget is None` and add an explicit `if budget == 0: return None` branch so the rule "null when zero" is testable separately from "null when None"; (c) stash `project.currency` in `ProjectCostSummary` and document the single-currency assumption.
  - Added: 2026-05-15 (calc-audit row #24)

- **Cost-to-date aggregation — base_rate=0 raises 500; checkpoint premise about hours×rate is wrong** — `backend/app/modules/tracker/services/cost_service.py:25-114` (per-part calc), aggregated by `backend/app/modules/tracker/services/aggregation_service.py:42-140` via `SUM(report_part.cost)`. **[base_rate=0 FIXED 2026-05-16 — commit `c4aaeac9`. Currency-mismatch sub-issue remains open, tracked under #24/#26.]**
  - Module: `tracker`
  - **Formula correction**: it is NOT `hours × hourly_rate`. The actual math is `cost = percentage × rate_value × dedication × (contract_rate / base_rate)`, where `percentage` ∈ [0,1] is fraction of month, `rate_value` is a *monthly* rate from `RateDB` (e.g. band B = 15365), `dedication` ∈ [0,1] is FTE fraction, and `contract_rate/base_rate` adjusts for project-specific pricing. The constant "20 days/month" feeds only `days`, never `cost`. There is no concept of hours in this path.
  - **Rate selection (good)**: rates are *frozen at write time*. When a `report_part` is created/updated, the user's current `rate_id`, the period's `base_rate`, and project's `contract_rate` are dereferenced and the resulting `cost` is persisted in `report_part.cost (Numeric(12,2))`. Later changes to user rate or period base_rate do NOT recost history. Historical preservation is correct.
  - **Bug — `base_rate=0` raises `ZeroDivisionError`**: `cost_service.py:37` does `contract_rate / base_rate`. The Pydantic schema accepts `Field(ge=0)` and the DB column has no `CHECK > 0`. Repro: create a `reporting_period` with `base_rate=0`, then try to create a `report_part` → 500 instead of validation error.
  - **Currency mismatch (same family as #24)**: confirmed. `RateDB` has no currency field; `rate_value` is implicitly in some currency (EUR by convention). `aggregation_service` sums `report_part.cost` directly into `project_cost_summary`, which is then displayed as `project.currency`. If a project is non-EUR and rates are EUR, totals are silently wrong-labeled. Same fix family as #24.
  - Other edge cases handled: percentage=None → cost=None; rate_id=None / dedication=None → cost=None (excluded from aggregate, not zeroed); deleted Rate row → cost=None; estimated/percentage≤0 parts → excluded; missing project settings → DEFAULT_RATE(175) fallback; DB CHECK `percentage∈[0,1]` + `cost >= 0`.
  - Minor: `contract_rate/base_rate` produces an unquantized Decimal; cost storage truncates to Numeric(12,2). Aggregate rounding error scales with row count but is bounded.
  - Tests today: `TestCalculateCostAndDays` covers the pure-math path (all 4 bands, contract>base, contract<base, zero-percentage, changed base_rate). `apply_cost_and_days` I/O paths and base_rate=0 are NOT covered.
  - Suggested:
    - `apply_cost_and_days_user_without_rate` (cost=None, no crash).
    - `apply_cost_and_days_base_rate_zero` — currently raises ZeroDivisionError; documents the bug.
    - `apply_cost_and_days_rate_change_does_not_recost_history` (pin the historical-freeze invariant).
    - `apply_cost_and_days_rate_missing` (FK orphan → cost=None).
  - Fix: add `Field(gt=0)` on `ReportingPeriodCreate.base_rate` (and DB CHECK) so the zero case is rejected at write. Document on `RateDB` that `rate_value` is EUR-monthly so callers can FX-convert when `project.currency != EUR` (cross-ref #24).
  - Added: 2026-05-15 (calc-audit row #25)

- **ECB currency conversion — no rate=0 guard, no historical lookup, no staleness check** — `backend/app/core/services/exchange_rate_service.py` (`convert_to_eur` :97, `get_latest_rate` :82, `currency_to_code` :30, `get_available_currencies` :112).
  - Module: `core/services`
  - Formula and direction are correct: `EUR = amount / rate` (rate stored as foreign units per 1 EUR, ECB convention). EUR passthrough short-circuits at `:100-101` and `:84-85`. Legacy `"dollar"` label normalized via `CURRENCY_NAME_MAP`. Negative amounts (refunds) handled by Decimal sign.
  - Issues:
    1. **rate=0 raises `decimal.DivisionByZero`** at `:109`. Repro: insert `ExchangeRateDB(currency_code="USD", rate=Decimal("0"))` (no DB CHECK > 0 either), call `convert_to_eur(100, "USD")` → unhandled exception.
    2. **No historical lookup**. Always uses the latest-stored rate (`order_by rate_date.desc().limit(1)` at `:90-91`). No `as_of: date | None` parameter. Tracker reports dated months ago will be FX'd at today's rate when #24/#25 are eventually wired through this service. **This is a blocker for the #24/#25 currency fix** — without historical lookup, calling this service would re-FX a 2024 report at 2026 rates and produce wrong totals.
    3. **No stale-rate warning**. If the daily 14:30 UTC cron silently fails for weeks, `get_latest_rate` returns a month-old rate with no warning. No max-age check on `rate_date`.
    4. **No None/empty-string guard**: `convert_to_eur(amount, None)` raises `AttributeError` on `.lower()`. `convert_to_eur(amount, "")` silently looks up empty code → None. Either both should validate or both should fail loudly.
    5. **Decimal precision** — `100 / 1.10` yields repeating digits at default `decimal` context (28 places). No `quantize` to a money scale; callers must format.
  - Existing tests: 9 tests added during the Tier-2 audit sweep (legacy-label normalization, EUR passthrough, divide-by-rate direction, missing-rate, ordering). The five issues above are not covered.
  - Suggested:
    - `test_convert_to_eur_zero_rate_guarded`: rate=Decimal("0"), amount=100 → expect None + warning log (NOT DivisionByZero).
    - `test_convert_to_eur_at_date(as_of)`: rate on 2024-01-15 ≠ today → conversion picks on-or-before-date row.
    - `test_get_latest_rate_stale_warning`: only rate >7 days old → still returned, emits stale-rate warning.
    - `test_convert_to_eur_negative_amount`: rate=1.10, amount=-110 → -100 (refund roundtrip pin).
    - `test_currency_to_code_empty_or_none`: "" / None → ValueError (or documented passthrough).
  - Fix order (smallest first):
    - Add `if rate == 0: logger.warning("exchange_rate_zero", currency=code); return None` at `convert_to_eur` (one-liner, defensive).
    - Add optional `as_of: date | None` parameter on `get_latest_rate` / `convert_to_eur` filtering `rate_date <= as_of`. Required before wiring #24/#25 through this service.
    - Log `exchange_rate_stale` warning if latest rate is >2 days old (alert ops separately).
  - Added: 2026-05-15 (calc-audit row #26)

- **Invoice effective_status — MAX(postponed_to) vs most-recent + Python/SQL duplication** — `backend/app/modules/tracker/services/invoice_status.py:28-54` (SQL CASE) + sibling Python `_invoice_status_info` at `backend/app/modules/tracker/api/invoices.py:56-62`. **[MAX-vs-most-recent FIXED 2026-05-16 — commit `9e8661b9`. Python/SQL deduplication deferred (semantic alignment kept; one source of truth would change blast radius).]**
  - Module: `tracker`
  - CASE structure (correct overall):
    - `status IN ('scheduled','pending_to_issue') AND pp.postponed_to > today` → `postponed`
    - `status IN ('scheduled','pending_to_issue') AND pp.postponed_to <= today` → `pending_to_issue`
    - `status = 'scheduled' AND due_date <= today` → `pending_to_issue`
    - ELSE → stored status (waiting_for_payment / paid / cancelled / scheduled-future)
  - Postponement subquery: `SELECT invoice_id, MAX(postponed_to) AS postponed_to, COUNT(*) FROM invoice_postponements GROUP BY invoice_id`. Boundary `postponed_to == today` → expired (`pending_to_issue`) because the postponed branch uses strict `> today`.
  - Issues:
    1. **MAX-by-date instead of most-recent-by-created_at**. If a later postponement record corrects the date closer in (e.g. earlier postponement `today+30`, later correction `today+5`), `MAX(postponed_to)` keeps the further-future date and the invoice stays "postponed" past its intended new date. Mostly safe if postponements only push outward, but a correction is silently ignored. Repro: create postponements [today+30, then today+5]; subquery returns today+30 → invoice stays postponed until the older far date.
    2. **Python/SQL duplication**: the SQL CASE is mirrored in Python (`_invoice_status_info` in `invoices.py:56-62`) for detail-endpoint responses. Two copies of the same rule = drift hazard.
    3. Timezone: `date.today()` is naive local-server date. Boundary day depends on server TZ vs client TZ. Same family as #23/#22 latent gotcha.
    4. Boundary `postponed_to == today` → `pending_to_issue` is consistent in the SQL but not pinned by any test.
  - Tests today: `test_postponements.py` covers transition blocks, postponement window, 30-day rule, delete-latest. NO test asserts:
    - boundary `postponed_to == today` resolves to `pending_to_issue`.
    - MAX-vs-most-recent behavior with non-monotonic postponements.
    - SQL CASE vs Python `_invoice_status_info` agreement on the same fixture.
    - admin list sort pushing paid rows last.
  - Suggested:
    - `test_effective_status_boundary_today` (postponed_to=today → pending_to_issue).
    - `test_effective_status_multiple_postponements_uses_max_date` (documents current MAX-wins behavior).
    - `test_invoice_status_info_python_matches_sql` (cross-check list vs detail endpoint on same fixtures).
    - `test_admin_list_sort_due_date_pushes_paid_last`.
  - Fix: change postponement subquery to `DISTINCT ON (invoice_id) ORDER BY invoice_id, created_at DESC` so "latest" reflects intent, not date magnitude. Deduplicate the Python copy by reusing the SQL expression (one source of truth) or by always going through the list endpoint's `effective_status`.
  - Added: 2026-05-15 (calc-audit row #27)

- **Postponement accepts a `postponed_to` in the past when base_date is even older** — `backend/app/modules/tracker/api/postponements.py:127-141`. **[FIXED 2026-05-16 — commit `f084e0de`]**
  - Module: `tracker`
  - Formula: `base_date = latest_postponement.postponed_to ?? invoice.due_date`; `window_base = max(base_date, today)`; valid range = `(base_date, window_base + 30 days]`. Upper bound is correct.
  - Repro of the lower-bound bug: due_date = today−10, POST `postponed_to = today−5`. The check `postponed_to <= base_date` is `today−5 <= today−10` → False (passes), and upper-bound check `today−5 > window_base + 30` is also False (passes). Result: 201, a postponement is created to a date already in the past. The invoice's effective status immediately flips back to `pending_to_issue`, so the postponement record is a no-op that confuses the audit trail.
  - Why it slipped through: validation compares against `base_date`, not against `window_base`. The "strict after" check enforces "after base_date" but not "after today".
  - Other edge cases handled correctly: base_date in past → window = today+30d; base_date == today → today+30d; second-postpone blocked while previous still active (`postponed` eff status); restack after previous expires; same-date submission rejected.
  - Tests today: 6 tests in `test_postponements.py` cover window math, base-date semantics, can't-postpone-already-postponed, delete-latest. The backdate case is not covered.
  - Suggested:
    - `test_postpone_to_past_date_rejected` (due_date=today−10, postponed_to=today−5 → 400; currently 201).
    - `test_postpone_exactly_at_window_boundary` (postponed_to=today+30 → 201; today+31 → 400).
    - `test_postpone_when_base_date_is_today` (today+30 → 201; today+31 → 400).
  - Fix: change the lower-bound check to compare against `window_base`, not `base_date`:
    `if body.postponed_to <= max(base_date, today): raise HTTPException(400, "New date must be after today and after the current due/postponed date")`.
  - Added: 2026-05-15 (calc-audit row #28)

- **Mood aggregation — estimated reports contaminate the average + trend silently skips current month + no `/trend` test** — `backend/app/modules/tracker/api/moods.py:38-217`.
  - Module: `tracker`
  - Monthly formula (`moods.py:96`): `average_mood = round(sum(non_null_moods)/len(non_null_moods), 1) if moods else None`. Distribution = `Counter(non_null_moods)`. `total_reports` counts all rows (including null-mood), `total_responses` counts only non-null. Correct math on null-mood exclusion.
  - Anonymity invariant verified: `AnonymousFeedbackDB` queried by `(month, year)` only; DELETE matches by `id` alone; schema-level tests (`test_anonymous_feedback_only_has_allowed_columns`, `test_anonymous_feedback_has_no_fk`) pin the contract. ✓
  - Issues:
    1. **`estimated=True` reports contaminate aggregation** (cross-ref #29's latent observation). `moods.py:88-92` and `:146-150` do NOT filter `ReportDB.estimated.is_(False)`. If an admin pre-creates estimated reports carrying stale mood from a prior cycle, they enter `average_mood`, `mood_distribution`, `named_feedback`, AND inflate `total_reports`. Per CLAUDE the mood dialog only writes mood on Confirm, so estimated reports *should* have mood=null in practice — but the code doesn't enforce this defensively.
    2. **Trend silently excludes the current month**. `_last_12_months` builds 12 months ending at *last completed* month. In May 2026 the trend returns May 2025 … Apr 2026 (no May 2026). Likely intentional ("only closed months"), but undocumented and UI may expect rolling-12 inclusive. Pin the contract with a test.
    3. **No `mood ∈ {1..5}` validation at aggregation time**. If a stray 0 or 6 ever lands in `reports.mood` (e.g. via direct DB write or a future schema change), it silently affects the average. Defensible to rely on DB CHECK + Pydantic, but a value-range filter at aggregation would be belt-and-braces.
    4. **No tests for `/trend` endpoint at all**. Trend formula, empty-month bucketing, year-boundary, named_feedback-per-month — all uncovered.
    5. Minor: `round(x, 1)` uses banker's rounding (`2.55 → 2.5`). `named_feedback` has no pagination bound.
  - Tests today: 6 tests for monthly endpoint (distribution, anon merge, named merge, admin gate, empty month). 2 schema tests for anonymity invariant. **0 tests for `/trend`.** No test for estimated-reports contamination, no test for null+non-null mix, no test for mood DELETE or anonymous DELETE.
  - Suggested (per agent):
    - `test_get_moods_excludes_null_mood_from_avg` (moods=[5,None,3] → avg=4.0, total_responses=2, total_reports=3).
    - `test_get_moods_trend_returns_12_months` (seed sparse months → exactly 12 entries chronological, empty months avg=None).
    - `test_get_moods_trend_excludes_current_month` (pin the design choice).
    - `test_get_moods_estimated_reports_excluded` (after fixing).
    - `test_delete_anonymous_feedback_unknown_404` + `_204` (idempotency contract).
  - Fix: (a) add `.where(ReportDB.estimated.is_(False))` at moods.py:90 and :149 to align with the rest of the burn/EVM rule; (b) decide and document whether `/trend` includes the in-progress month, add the test that pins the choice.
  - Added: 2026-05-15 (calc-audit row #30)

- **Period rotation cron is not idempotent on day 15** — `backend/app/worker/rotate_reporting_period.py:39-81` (rotate logic), `:40` (day-15 guard), `backend/app/worker/settings.py:143` (`cron(rotate_reporting_period, day=15, hour=0, minute=0)`). **[FIXED 2026-05-16 — commit `9921bcaf`]**
  - Module: `tracker`
  - **Premise correction**: the "45-day offset" mentioned in the checkpoint exists only in the frontend (`Moods.tsx:80`) for the mood admin page's default month. The *backend* rotation is purely calendar-driven by cron firing on the 15th at 00:00 UTC — no offset arithmetic. "Current period" is DB-driven via `status=ACTIVE` flag.
  - **Idempotency bug**: if the cron fires twice on day 15 (worker restart at midnight, manual retrigger, ARQ retry, etc.) AND the freshly-created period is already ACTIVE:
    - First run: finishes previous active period, creates the new one, activates it.
    - Second run: `get_active_period(db)` returns *the new one we just created*; line 60-65 calls `finish_period(active.id)` on it — flipping the freshly-rotated period to FINISHED. Then the `if existing_period.status != ACTIVE` branch is skipped (already ACTIVE → not re-activated), so the period ends up FINISHED with no replacement.
    - The existing `test_noop_when_current_month_already_active` test only passes because the fixture's active period is February, not the just-rotated March — so the bug isn't exercised.
  - Other gaps:
    - **No catch-up**: if the worker is down on the 15th, day 16's run hits `day != 15` and skips. The period stays on the old month until manual intervention. No alert.
    - **Timezone drift**: `date.today()` is server-local; ARQ cron is UTC. Fine in current UTC container, but a future Docker TZ change would shift the boundary.
    - **Year boundary** is actually safe (`today.replace(day=1)` preserves year/month), no Dec→Jan month=13 issue.
    - Relies on the Pydantic first-of-month validator at `schemas/reporting_period.py:16-19,26-31` to normalize `date=today (day=15)` → `day=1`. If that validator is ever removed, the unique-on-first-of-month invariant breaks.
  - Tests today: 6 tests in `test_rotate_reporting_period_job.py` cover guard + happy path + no-active + pre-created + same-month-already-active + job-run record. None cover the **double-run idempotency case**, the missed-15th case, or the year boundary.
  - Suggested:
    - `test_idempotent_second_run_same_day` — pre-seed active period for current month (Mar 1), run rotate twice on Mar 15, assert period still ACTIVE on second run.
    - `test_active_period_for_current_month_not_finished` — explicitly assert the guard.
    - `test_dec_to_jan_year_boundary` — mock today=2026-12-15, pre-seed active Nov 1, assert new period Dec 1 2026 created (and document that Jan rotation requires Jan 15 to fire).
    - `test_first_of_month_normalization_in_create_period` — assert created `period.date.day == 1` even when `ReportingPeriodCreate(date=today)` passes day=15.
  - Fix (one line): guard before `finish_period`:
    `if active and active.date != new_date: await finish_period(active.id)`. Repeat runs on the 15th no longer flip the freshly-created month's period to FINISHED.
  - Added: 2026-05-15 (calc-audit row #31)

- **Capacity FA averages — partial reporters drag the average down; over-reporters not clamped; internal/admin invisible** — `backend/app/core/services/capacity_insights.py:388-417` (`_aggregate_fa_period`), user query at `:316-318`, per-user totals at `:326-349`, on-leave skip at `:403`.
  - Module: `capacity` (lives in `core/services` because it's a cross-module analytical view)
  - Formula: `avg_billable_pct = sum(user.billable_pct) / count(users where total_pct > 0)`, same shape for `avg_absence_pct`. Each `user.X_pct` is a sum of `ReportPartDB.percentage` segmented by `ProjectDB.is_billable` / `is_absence`. `estimated` reports are intentionally included (per CLAUDE rule, confirmed by row #29).
  - Filters work as documented: `UserDB.active=True`, `requires_project_reporting=True`, FA in the 6 target FAs, total_pct > 0 (drops on-leave). FAs with 0 eligible users are omitted from the response entirely (not returned as 0).
  - Issues:
    1. **Partial reporters skew the average without warning**. The formula uses raw per-user totals, not per-user ratios-of-reported. Repro: FE has 2 users; A reports parts summing to 1.0 with billable=0.8, B reports a single billable=0.3 part (didn't fill the rest). `avg_billable = (0.8 + 0.3) / 2 = 0.55`. If both reported in full, A=0.8 and B's 0.3 would imply B's true billable share is unknown — the result silently penalises FE for B's incomplete report.
    2. **Over-reporting (sum > 1.0) not clamped**. A user filling 1.2 in parts contributes 1.2 to the numerator. No warning, no clamp.
    3. **Internal/admin invisible**. Projects flagged neither `is_billable` nor `is_absence` (e.g. internal initiatives, training, ops admin) feed `total_pct` but NOT `avg_billable_pct` or `avg_absence_pct`. So `billable + absence < total` silently — the FE cannot tell "low billable because lots of internal" from "low billable because few projects". No `internal_pct` (or `other_pct`) field exposed.
    4. **Active-but-zero-billable**: a user who only reports absence (e.g. 0.4 sick leave) counts in the denominator but contributes 0 to billable_pct. Distinct from total=0 (excluded). Consistent, but documents that "FA billable average" mixes apples (full reporters) with oranges (mostly-out reporters).
    5. **No mutual-exclusion check between `is_billable` and `is_absence`**. A project flagged both would double-count.
  - Tests today: 7 tests in `test_capacity_insights.py::TestGetCapacityInsights` cover the happy path (`test_billable_pct_averaged_across_users`), non-reporting exclusion, on-leave exclusion, target-FA filter, absence separation, multiple periods.
  - Suggested:
    - `test_partial_reporter_drags_fa_average_down` (lock the current behavior with the 0.55 example, or change to per-user ratio normalization).
    - `test_over_reporting_user_not_clamped` (1.2 → contributes 1.0 to numerator).
    - `test_user_with_only_internal_work_drags_billable` (total=1.0, billable=0, absence=0 → counted, billable_pct contribution=0).
    - `test_inactive_user_excluded` (active=False with full report → not counted).
    - `test_estimated_report_included` (lock CLAUDE rule).
  - Fix (pick one):
    - (a) Normalize per-user contribution by dividing by `total_pct` (`avg_billable = mean(billable / total)`), so each user weighs equally regardless of how much they reported.
    - (b) Or keep raw averages but surface `avg_total_pct` + `avg_internal_pct` so the FE can detect underreporting and expose the gap. This preserves the current semantic.
  - Added: 2026-05-15 (calc-audit row #33)

- **Capacity user detail — same project shows twice when split across FAs + no gap segment for partial reporters + sum=1.0 invariant only enforced at Confirm** — `backend/app/core/services/capacity_insights.py:225-271` (user detail), `:116-148` + `:161-168` (FA detail). Confirm gate at `backend/app/modules/tracker/api/reports.py:180-194` (`math.isclose(total, 1.0, rel_tol=1e-4)`). Report-part unique constraint at `backend/app/modules/tracker/models/report_part.py:21` = `(project_id, report_id, functional_area_id)` — NOT unique on `(project_id, report_id)`.
  - Module: `capacity`
  - Issues:
    1. **Duplicate row when same project is split across FAs**. The user-detail SQL returns one row per `ReportPartDB` (no `GROUP BY (period_id, project_id)`). A user reporting Project A as FE=0.4 and Project A as BE=0.3 (allowed by the FA-aware unique constraint) renders in the response as two separate entries `{"name":"A", "percentage":0.4}` and `{"name":"A", "percentage":0.3}` instead of one consolidated `{"name":"A", "percentage":0.7}`. **FA detail aggregates correctly** via SQL SUM, so the bug is user-detail-specific. Repro: parts (A, FE, 0.4) + (A, BE, 0.3) → user detail returns two rows; FA detail returns 0.7 in one row.
    2. **Partial reporters' gap is invisible** (sister of #33 finding for averages). A user with a single `ReportPart(percentage=0.3)` on one billable project shows that project at 30% and the remaining 70% disappears. UI cannot distinguish "user only worked 30% of a month" from "user only filled out 30% of their report".
    3. **Over-reporter not clamped**. Parts summing to 1.2 → all percentages rendered raw, stacked-bar overflows 100% with no flag.
    4. **Sum=1.0 invariant only enforced at the estimated→false transition**. Once confirmed, editing a part can break the invariant without re-validation. No hook re-checks `total ≈ 1.0` on subsequent PATCH/PUT.
    5. **Internal/admin work hidden in user detail too** (same as #33). `test_excludes_non_billable_projects` is currently *locked in as expected behavior*; that test itself documents the hide-internal bug.
    6. `billable_project_count` counts DISTINCT project_id even when percentage is 0 (filters NULL not 0). User with `0.0` part on a billable project gets `count=1, billable_pct=0`.
  - Tests today: 5 tests on user/FA detail (per-project happy path, exclude-non-billable, absence rollup). Missing: duplicate-project-multi-FA, partial-reporter gap, over-reporter clamp, edit-after-confirm sum drift, internal_pct surfacing.
  - Suggested:
    - `test_user_detail_dedups_same_project_multi_fa` (parts (A,FE,0.4) + (A,BE,0.3) → one row `{"name":"A", "percentage":0.7}`). **Would fail today.**
    - `test_partial_reporter_surfaces_unreported_gap` (parts=[0.3 billable] → response includes `unreported_pct=0.7` or equivalent).
    - `test_over_reporter_clamped_or_flagged` (parts=[0.7, 0.5] → `total_pct=1.2` returned, UI can flag).
    - `test_confirmed_report_sum_invariant_after_edit` (confirm at 100% then PATCH part → assert re-validation or alert).
    - `test_internal_project_pct_surfaced` (parts=[0.5 billable, 0.5 internal] → user detail surfaces internal explicitly).
  - Fix: in `get_capacity_user_detail`, `GROUP BY (period_id, project_id)` at the SQL layer with `SUM(percentage)` so multi-FA parts collapse to one row. Add `other_pct` paralleling `absence_pct` for non-billable-non-absence work. Compute `unreported_pct = max(0, 1 - billable_sum - absence_pct - other_pct)` so partial reporters surface a "Unreported" segment. Return raw `total_pct` so the UI can flag over-reporters.
  - Added: 2026-05-15 (calc-audit row #34)

- **Reportable-users filter inconsistent — 3 paths leak inactive/exempt users** — `backend/app/core/services/capacity_insights.py:627` (`get_allocation_projects`), `backend/app/modules/capacity/api/planner.py:179` (planner main query), `capacity_insights.py:197` (`get_capacity_user_detail`).
  - Module: `capacity`
  - The CLAUDE rule (`active=True` + `requires_project_reporting=True` + on-leave skip) is correctly applied in: `get_capacity_insights`, `get_capacity_fa_detail`, `get_reportable_users`, `get_allocation_users`, `planner._add_empty_groups`, `planner` by-project view.
  - Leaks:
    1. **`get_allocation_projects`** (used by allocation "By Project" chart) — joins `UserDB` via `ReportDB.user_id` but does NOT filter `UserDB.active` or `UserDB.requires_project_reporting`. Inactive or exempt users with `ReportPartDB` rows on a live billable project appear as segments. Repro: deactivate a user who has logged time, query allocation projects → user still shows in the segment legend.
    2. **`planner.py:179`** (main allocation query) — filters `UserDB.active=True` but NOT `requires_project_reporting=True`. Asymmetric with `_add_empty_groups` (line 127-128) which filters both. So a non-reporting user with `CapacityPlanDB` rows can show up in the data path but never get an empty-row placeholder. Repro: set `requires_project_reporting=False` on a user with plan entries → user appears in main query data, missing from empty-groups.
    3. **`get_capacity_user_detail`** (`GET /api/capacity/insights/user-detail`) accepts any `user_id` with no gating. Only the FE selector restricts the choice; a direct API call with an inactive or admin user_id returns data instead of 404/empty. Backend trusts the FE.
  - Edge cases otherwise handled: exempt users with reports excluded from insights/FA-detail/allocation-users/empty-groups; inactive users with recent reports filtered in same five; on-leave (total_pct=0) dropped from FA averages but denominator preserves meaning. Also note: `get_reportable_users` has NO FA scoping, so users in non-target FAs (e.g. "DevOps") appear in the selector but yield sparse downstream views — UX-only inconsistency.
  - Tests today: cover `get_reportable_users` (active+reporting filter), `get_capacity_insights` exempt-user exclusion, `get_capacity_fa_detail` exempt-user exclusion, `get_allocation_users` both filters. **No tests** on `get_allocation_projects` user-filter, planner main query, or `get_capacity_user_detail` with non-eligible user_id.
  - Suggested:
    - `test_allocation_projects_excludes_inactive_user_segments` + `_excludes_exempt_user_segments` (would fail today).
    - `test_planner_main_query_excludes_exempt_users` (asymmetric with `_add_empty_groups`).
    - `test_user_detail_returns_empty_for_inactive_user` + `_for_exempt_user`.
    - `test_reportable_users_excludes_non_target_fa` (or document the selector is FA-agnostic).
  - Fix:
    - Add `UserDB.active.is_(True)` + `UserDB.requires_project_reporting.is_(True)` to the join in `get_allocation_projects` (~line 662).
    - Add `UserDB.requires_project_reporting.is_(True)` to `planner.py:179`.
    - Gate `get_capacity_user_detail` with a `UserDB` existence check (`active + reporting`) returning `[]` (or 404) for non-eligible user_id.
  - Added: 2026-05-15 (calc-audit row #35)

- **On-leave detection: "total=0" semantic too narrow; full-PTO reporters drag FA averages** — `backend/app/core/services/capacity_insights.py:159` (FA detail), `:403` (FA aggregator), `:602-604` (allocation_users).
  - Module: `capacity`
  - Current definition: `total_pct = SUM(percentage)` over a user's non-NULL parts ≤ 0 → "on leave / didn't report" → excluded. Catches: no report at all (LEFT-join miss); report with all parts=0 or NULL; orphan ReportDB. Estimated reports with sum>0 count as "reporting" (per CLAUDE / row #29).
  - **The semantic is too narrow**. A user on full PTO who diligently logs `ReportPart(absence_project, 1.0)` is statistically equivalent to one who logged nothing — but the two are treated oppositely. The diligent one is counted in the FA average with `billable_pct=0`, dragging the FA mean down. Repro: seed FA-FE user with a single `ReportPart(absence_project, 1.0)` for Jan → FA-FE billable_pct drops; not excluded.
  - Inconsistency across endpoints: FA detail + FA aggregator use `total_pct <= 0`. `get_allocation_users` uses "user has any report row in period range" (`proj_map` truthy). Subtle drift, but mostly equivalent.
  - Tests today: 3 tests cover no-report, all-zero-parts, FA detail mirror. None cover the full-absence case.
  - Suggested:
    - `test_user_full_absence_not_on_leave` (lock the current behavior or document the bug).
    - `test_estimated_report_with_data_counts_as_reporting` (pin CLAUDE rule).
    - `test_estimated_zero_report_excluded` (estimated flag orthogonal to on-leave).
    - `test_under_reported_user_not_on_leave` (0.3 billable → still counted).
  - Fix (product decision): if "all-absence = on leave", change gate to something like `billable_pct > 0 OR (absence_pct == 0 AND total > 0)`. If not, document explicitly in CLAUDE.md that filed-full-PTO lowers the FA billable average by design — and consider an `internal_pct`/`absence_pct` average so consumers can read context, not just a depressed billable number (cross-ref #33 same fix).
  - Added: 2026-05-15 (calc-audit row #36)

- **TypeScript types lie about Decimal-as-string wire format** — Events types (`frontend/src/modules/events/types/events.ts:40-41,123`), Rate type, untyped Stats response.
  - Module: `events` (most exposed), cross-cutting on every endpoint that returns a Pydantic `Decimal` without explicit `float` coercion.
  - Background (per memory `gotcha_pydantic-decimal-serialization.md`): Pydantic `Decimal` serializes as JSON string by default. The FE must `Number(x)` before arithmetic or `.toFixed`. Tracker / Scorecard / Project schemas dodge this by coercing to `float` at the boundary (e.g. `EVMData.budget_total: float`), so their TS types are honest. **Events does not**: `EventDetail.total_cost`, `event.other_costs`, `EventAttendee.cost`, `stats.total_cost`, and `Rate.value` are all `Decimal` server-side but typed as `number` on the FE.
  - Call sites mostly survive *only* because defensive `Number(...)` calls were sprinkled in: `EventDetail.tsx:68-69/201`, `EventCard.tsx:92`, `EventsTable.tsx:135`, `EventForm.tsx:83/166`, `ProjectTrackerDetail.tsx:65-66`, `RatesContent.tsx:120/52/57`. The pattern works today but is one careless refactor away from a NaN or string-concat bug, because tsc allows everything (the types claim it's already a `number`).
  - Specific latent hot spot: `StatsCharts.tsx:152` passes `stats.total_cost` straight into `formatCurrency` (which calls `Intl.NumberFormat.format(value)`). It works only because `Intl.NumberFormat.format` does ToNumber coercion internally. If anyone later does `stats.total_cost + somethingElse` they'll concatenate.
  - **Premise refinement for #20**: `BurnDashboard.tsx:277` `staff + nonStaff` is NOT vulnerable — those come from `ProjectCostSummary` which serializes as `float` server-side (`schemas/project_cost.py:12-13`). Same for `PerformanceCard.tsx:311` arithmetic on `evmData.*`. Audit row #20's comment on "no test imports formatCurrency" still holds, but the BurnDashboard arithmetic is safe.
  - Tests today: zero. Existing event/rate/stats fixtures use number literals (not the actual string wire format), so tests cannot catch a regression where someone drops a `Number()` wrapper.
  - Suggested:
    - `EventsTable renders total_cost when wire format is string` (fixture `{ total_cost: "3911.03" }` → renders "€3911.03").
    - `EventDetail handles string total_cost/other_costs/a.cost` (no NaN).
    - `StatsCharts.total_cost as string "1234.5" → formatCurrency renders correctly`.
    - `EventForm with existing event.other_costs="100.00" string → totalCost arithmetic does not concatenate`.
    - `RatesContent rate.value="750.00" string → display "750.00"` (not "750.00.00").
  - Fix: change the lying TS types (`total_cost: number` → `string`, etc.) so tsc forces every consumer to call `Number(x)` explicitly. StatsCharts.tsx:152 becomes a tsc error pointing to the missing coercion. Alternative: coerce to `float` at the Pydantic boundary on the backend (mirror the tracker/scorecard pattern) — moves the discipline server-side and keeps wire types honest.
  - Added: 2026-05-15 (calc-audit row #38)

- **Capacity charts default to oldest 6 months instead of latest** — `frontend/src/modules/capacity/components/ChartPagination.tsx:11-21`, consumers `InsightsChart.tsx:40`, `FADetailChart.tsx:99`, `UserDetailChart.tsx:89`.
  - Module: `capacity`
  - Math is sound: window size = 6 (`MAX_VISIBLE`), disjoint pages (`start = safePage * 6`), `safePage = min(page, totalPages-1)`, `null` returned when `totalPages === 1`. No off-by-one in the slice itself.
  - **UX bug**: all three chart consumers initialize `useState(0)` → page 0 → `data.slice(0, 6)`. Backend returns chronological ascending, so the user opening Insights / FA Detail / User Detail sees months from 6+ ago and must click `>` repeatedly to reach the current period. The expected default for an operations dashboard is "latest window first".
  - Other latent gaps:
    - Negative `page` (`-1`) would silently produce `slice(-6, 0) = []` — unreachable today because buttons disable at `safePage===0`, but the hook itself doesn't clamp the lower bound.
    - `data.length === 7` yields a lone trailing page with one bar on a wide chart (disjoint pages, no sliding window) — minor visual surprise.
    - `safePage` is computed locally but never synced back to the parent `page` state; if `page` drifts above `totalPages-1`, the local state stays stale.
  - Tests today: **none** for `ChartPagination`. The only `paginate*` tests target the different `ProjectAllocationList` / `UserAllocationList` (show-more lists), not the chart window.
  - Suggested:
    - `useChartPagination empty data → { visible: [], totalPages: 1, safePage: 0 }`.
    - `useChartPagination 7 items → page 0 has 6, page 1 has 1`.
    - `useChartPagination 12 items, page 1 → disjoint from page 0`.
    - `useChartPagination page > totalPages-1 → clamped via safePage`.
    - `ChartPagination renders null when totalPages === 1`.
    - `InsightsChart default page lands on the latest window when data.length > 6` (regression guard for the default-oldest UX bug).
  - Fix: initialize page to last window in each chart consumer, e.g. `useState(Math.max(0, Math.ceil(chartData.length / 6) - 1))`, or a `useEffect` that sets `page = totalPages-1` when data length changes. One-liner per consumer (3 sites). Alternative: change default inside the hook itself so all chart consumers benefit at once.
  - Added: 2026-05-15 (calc-audit row #39)

- **Final-score weights are not validated at runtime; misconfig fails silently** — `backend/app/modules/scorecard/services/calculators/final_score.py:50-127` (consumer) + `backend/app/config.py:274-350` (`ScoringConfig.validate_weights` — informational only, never raises).
  - Module: `scorecard`
  - Repro: edit `config_parameters` row `weight_global_time = 0.5` and leave siblings untouched so the global group sums to 0.7 — calculator still produces a defensible-looking number by normalizing internally; no warning, no log. Similarly, setting all global weights to 0 yields `final = 0` indistinguishable from a real zero score, and a negative weight produces arbitrary results.
  - Detail: the calculator divides by `sum(config_weights for available dims)`, so any positive scaling is silently absorbed. `validate_weights()` exists but returns a dict that nobody inspects; startup does not reject bad configs.
  - Fix: at startup (in `load_scoring_config_from_db` or its caller) call `validate_weights()` and `logger.warning("scoring_weights_misconfigured", group=..., total=...)` for any group where `abs(total - 1.0) > 0.001`. Optionally refuse to boot in production. Reject negative/zero individual weights.
  - Added: 2026-05-15 (calc-audit row #4)

### OK
_(record explicit confirmations here so you don't re-audit later)_

- **SPI normalization** — `backend/app/modules/scorecard/services/calculators/time_calculator.py:32` — single-anchor `value/ideal` map; matches CLAUDE rule (SPI 0.85 → 85 pts).
  - Formula: `spi_norm = clamp(spi/ideal, 0, 1)`; `time_score = round(100 * weighted_avg([(0.6, spi_norm), (0.4, milestones_norm)]))`. Target is UI-only; not consumed by the calculator.
  - Edge cases handled: None (redistributes weights), 0 (→0 pts), >ideal (cap 1.0), negative (floor 0), `ideal<=0` short-circuit (no div-by-zero), all-None inputs (→ None).
  - Tests: `test_calculators.py::TestNormalizeToIdeal` (ideal=0, negatives, >ideal, zero), `TestGetIdeal::*`, `TestTimeCalculator::*` (perfect, no-data, only-SPI, only-milestones, partial). Coverage strong.
  - Suggested low-priority additions: `test_spi_zero_floors_to_zero_contribution`, `test_spi_very_high_caps_at_ideal`, `test_spi_negative_floors_to_zero_in_calculate`.
  - Audited: 2026-05-15 (calc-audit row #1)

- **CPI normalization** — `backend/app/modules/scorecard/services/calculators/cost_calculator.py:27` — `_normalize_to_ideal(cpi, ideal=1.0)`, same helper as SPI.
  - Formula: `clamp(cpi/ideal, 0, 1)` combined with budget_variance via `_weighted_average([(0.7, cpi_norm), (0.3, variance_norm)])`, then scaled 0-100.
  - Same-as-SPI: yes — mechanically identical pattern in TimeCalculator/CostCalculator. Target only drives UI color.
  - Edge cases handled: None, 0, >ideal (cap 1.0), negative (floor 0), `ideal<=0` short-circuit, 0/0 → None, all-None → None.
  - Tests: `TestNormalizeToIdeal` (full matrix), `TestGetIdeal::test_get_ideal_cpi`, `TestCostCalculator::*` (perfect, over-budget, no-data, only-CPI, only-variance, low-CPI), integration `test_cpi_calculation_from_evm`.
  - Suggested additions: `test_high_cpi_capped_at_100` (cpi=2.0 → 100), `test_zero_cpi_with_perfect_variance` (cpi=0.0,var=0.0 → 30), `test_negative_cpi_treated_as_zero`.
  - Audited: 2026-05-15 (calc-audit row #2)

- **budget_variance returns None when cost_to_date ≤ 0** — `backend/app/modules/scorecard/services/normalizers/indicators.py:88-94` (the None branch); calculator consumer at `backend/app/modules/scorecard/services/calculators/cost_calculator.py:28-32`.
  - Upstream producer: `MetricsBase._build_evm_data` (`backend/app/modules/scorecard/models/metrics/schemas.py:131-140`); `budget_variance` is derived per-request, never stored.
  - Formula: raw = `max(0, cost_to_date/budget_total - 1)` when both >0 else None; component = `max(0, 1 - raw)`; combined with CPI via `_weighted_average([(0.7, cpi), (0.3, variance)])`.
  - Callers: backend None-handled via `_weighted_average` (drops + redistributes); API ships `number | null` (`indicators.py:12`); frontend types match (`frontend/src/modules/scorecard/types/scores.ts:53`); only frontend display is `ScorecardTable.tsx:59` and renders "—" for null. No runtime arithmetic on `.budget_variance` anywhere on the FE.
  - Edge cases handled: `cost_to_date=0` (None), `cost_to_date<0` blocked by Pydantic `Field(ge=0)`, `cost_to_date=None` triple-guarded, `budget_total=None` triple-guarded, overrun floored at 0, very-high variance auto-capped.
  - Minor edge case noted (out of scope for the rule): `budget_total=0` with `cost_to_date>0` falls through to `normalize_budget_variance` and yields 1.0 (perfect variance). Data-quality scenario; flag if it surfaces in real projects.
  - Tests: helper-level `TestBudgetVariance` covers `normalize_budget_variance` exhaustively; calculator-level `TestCostCalculator` covers over-budget, no-data, only-CPI, only-variance — but **the specific `_calculate_budget_variance` returns-None-on-zero-cost branch is not directly tested**.
  - Suggested additions: `test_calculate_budget_variance_returns_none_when_cost_to_date_zero`, `test_calculate_budget_variance_returns_none_when_budget_only`, `test_cost_score_with_zero_cost_uses_cpi_only` (regression: cost-only unstarted projects must not score 100 on variance).
  - Audited: 2026-05-15 (calc-audit row #3)

- **Flow dimension calculator** — `backend/app/modules/scorecard/services/calculators/flow_calculator.py:26-70` — 5-component weighted composite, not a single "active/total" efficiency ratio.
  - Note: the checkpoint described this as "flow efficiency / active_time / total_time, beware /0" — that indicator does NOT exist in the codebase. Flow dim is `lead_time(0.35) + commitment_reliability(0.25) + pr_size(0.15) + review_turnaround(0.10) + deployment_frequency(0.15)`.
  - Components/units (all match between collector and target):
    - lead_time_days (lower-better), target in days
    - commitment_reliability (already 0..1, ge=0 le=1, pass-through)
    - pr_size_median lines (lower-better)
    - review_turnaround_hours (lower-better)
    - deployment_frequency releases/day (higher-better, capped at target)
  - Edge cases handled: all-None → None, weight redistribution, value≤0 with lower-better → 1.0 (perfect), value>target naturally bounded by `min(1.0, ratio)`, Pydantic `ge=0` blocks negatives everywhere.
  - **Caveat**: `lead_time_days` is consumed from the same Jira collector audited under #7. Within Flow, units are consistent (collector emits business days, flow target is also "days" of the same meaning). The unit-confusion bug only surfaces at the DORA classifier in `dora.py`. So Flow is OK *given the producer's contract*; fixing #7 may shift Flow numbers too.
  - Tests: `TestFlowCalculator` covers only-lead-time, slow-lead-time penalty, all-missing → None, happy path.
  - Suggested low-priority additions: `test_zero_deployment_frequency` (≈85 expected), `test_lead_time_well_above_target` (no underflow), `test_partial_inputs_redistribute`.
  - Audited: 2026-05-15 (calc-audit row #8)

- **Quality dimension calculator** — `backend/app/modules/scorecard/services/calculators/quality_calculator.py:7-101`. 8 components, weights sum to 1.00.
  - Components (weight, normalization, unit): defect_density (0.05, lower-better, /100 tasks), escaped_rate (0.15, lower-better, /100 tasks), mttr (0.05, lower-better, hours), story_review (0.25, ratio 0..1 passthrough), governance (0.20, ratio 0..1), pr_review (0.10, ratio 0..1), change_failure_rate (0.15, lower-better, percent 0..100), post_contract_tasks (0.05, lower-better, raw count).
  - Unit consistency: all targets match producer scales. CFR is percent (target 15 against producer's `*100`).
  - CLAUDE alerts-toggle rule honored: Quality only consumes `IndicatorsCreate`; `has_dependabot_alerts` / `has_budget_alerts` never read here. Score is independent of Slack-mute toggles.
  - Note on premise correction: the checkpoint mentioned "security vulnerabilities" — that field lives in `RiskCalculator`, not Quality. Recorded for the auditor of #10.
  - Edge cases handled: all-None → None, weight redistribution, lower-better with value=0 → 1.0, Pydantic `ge=0` blocks negatives, ratio components have `le=1` upstream so >1.0 inputs are rejected.
  - Cross-reference to #5: a caller mistakenly sending CFR as 0..1 (e.g. 0.15) instead of percent (15) → normalizer sees `target/0.15 → clamped 1.0 → perfect score`. The `le=100` recommendation from #5 doesn't catch the under-1 case; an additional sanity check (`>=1 ` when target is in percent) would, but is outside the scope of this row. Logged.
  - Tests: `TestQualityCalculator::*` covers perfect, partial, sev1 cap, no-data, defect density penalty, story-review-only.
  - Suggested: `test_change_failure_rate_at_double_target` (CFR=30, others perfect → 92), `test_post_contract_tasks_threshold` (count=6, others perfect → 98), `test_governance_only_partial` (governance=0.5 alone → 50).
  - Audited: 2026-05-15 (calc-audit row #9)

- **Satisfaction dimension calculator** — `backend/app/modules/scorecard/services/calculators/satisfaction_calculator.py:27-48`. 2 manual components, weights sum to 1.00.
  - Components: `client_satisfaction` (weight 0.90, target 0.85, ratio 0..1) and `pm_satisfaction` (weight 0.10, target 0.85, ratio 0..1). Both Pydantic `ge=0 le=1`.
  - Targets stored as percentages in config (e.g. 85) and divided by 100 at `base.py:28-29` so they live in the same 0..1 scale.
  - Edge cases handled: all-None → None, single-component redistribution, value > target capped at 1.0, Pydantic enforces bounds, zero is preserved as a legitimate "very unhappy" signal (distinct from None).
  - Latent (not in scope of audit row): if config target=0 (admin sets "zero tolerance" on satisfaction, unusual), `_normalize_to_target` returns 1.0 for any positive value — same observation surfaced under #9/#10 for the helper. Not satisfaction-specific.
  - Tests: `TestSatisfactionCalculator::*` covers full + partial + no-data + perfect. Missing: `test_zero_is_real_score`, `test_below_target_not_capped`, `test_partial_zero`.
  - Audited: 2026-05-15 (calc-audit row #11)

- **Value dimension calculator** — `backend/app/modules/scorecard/services/calculators/value_calculator.py:27-30`. Single-component, no weighted average.
  - Component: `okr_impact` only (StrategicImpact enum Low/Med/High/Trans → normalized at `normalizers/indicators.py:239-250` to 0.25/0.55/0.80/1.0). Calculator passes through `_to_score`. ROI intentionally excluded (docstring) to avoid double-counting with CPI/SPI.
  - Pydantic `ge=0 le=1` on the indicator field.
  - Edge cases handled: None → None, 0.0 preserved as legitimate score, out-of-range rejected at Pydantic.
  - Minor observations (not blockers):
    - Config row `weight_value_okr_impact` exists but is never consulted — dead config. Admin edits have no effect.
    - Unknown StrategicImpact enum falls through to `NEUTRAL_VALUE` (0.5) at `normalizers/indicators.py:250` instead of None — violates "missing excluded, not neutralized" rule in spirit. Currently unreachable because Pydantic StrEnum rejects unknowns at the boundary; treat as latent-only.
  - Tests: `TestValueCalculator::*` covers Trans/High/Med/Low + no-data. Missing: `test_zero_impact_returns_zero_not_none`, `test_value_above_one_rejected_by_pydantic`, `test_unknown_strategic_impact_normalizes_to_none` (would currently fail, exposing the NEUTRAL_VALUE fallback).
  - Audited: 2026-05-15 (calc-audit row #12)

- **Engineering dimension calculator** — `backend/app/modules/scorecard/services/calculators/engineering_calculator.py:24-50`. 3 manual components, weights sum to 1.00.
  - Components: `test_maturity` (0.50, target=0.60), `pr_review_ratio` (0.20, raw passthrough, implicit target=1.0), `arch_checklist` (0.30, target=0.80). All Pydantic `ge=0 le=1`. Targets stored as 0..100 in config, divided by 100 to match indicator scale.
  - Not Sonar-fed (Sonar coverage flows into Quality, not Engineering). All inputs are manual/judgement.
  - Edge cases handled: all-None → None, single-component redistribution, value > target capped at 1.0, Pydantic bounds enforced.
  - Minor observations (non-blockers):
    - `pr_review_ratio` is the only component without a configurable target — design asymmetry vs `test_maturity` / `arch_checklist`. If someone wants `target_pr_review=0.9`, no hook exists.
    - Stale comment in `test_partial_data_redistributes_weights` says "vs target=1.0" but actual config target is 0.80; test passes only because value 1.0 caps either way.
  - Tests: `TestEngineeringCalculator::*` covers perfect, no-data, single-component, partial, low-maturity. Missing: `test_arch_checklist_below_target`, `test_pr_review_passthrough_low`, `test_pr_review_only_weight_redistribution`.
  - Audited: 2026-05-15 (calc-audit row #13)

- **Disabled governance toggle does NOT zero scores (path B fully wired)** — `backend/app/modules/scorecard/services/calculators/dimensions.py` and the scorecard calc path.
  - The historical CLAUDE rule "disabled governance tool → 0 not neutral" was deliberately *not* implemented (per prior audit-warnings-followup decision). Path B chosen: keep scores unaffected, badge the UI instead. Verified.
  - `has_dependabot_alerts` and `has_budget_alerts` appear ONLY in: notification workers (`worker/check_dependabot.py:167`, `worker/check_business_alerts.py:174`), project CRUD (`projects_v2.py`, `core/models/project.py`), migration `022_add_alert_flags.py`, frontend project form, and the two badge components. Zero references in `services/calculators/`, `services/normalizers/`, or any score-producing service.
  - Badges confirmed: `AlertsOffBadge` (`QualityMetricsGrid.tsx:56`, rendered on `!has_dependabot_alerts`) and `BudgetAlertsOffBadge` (`EVMSection.tsx:25`, rendered on `!budgetAlertsEnabled`). Both pure presentational; tooltips state "alerting muted, score unaffected".
  - CLAUDE.md is already aligned — the stale "disabled → 0" line is not present (line 152 has only the correct "missing indicators are excluded, not penalized" rule). No doc-debt remains on this rule.
  - Suggested invariant tests (low priority, not blockers): `test_score_unaffected_by_dependabot_alerts_flag`, `test_score_unaffected_by_budget_alerts_flag`, plus the symmetric worker-filter tests. These would pin "alert toggle does not move score" as an explicit invariant.
  - Audited: 2026-05-15 (calc-audit row #15)

- **Schedule Variance (SV = EV − PV) not implemented — SPI is the substitute** — `frontend/src/shared/utils/evmCalculations.ts:15` (SPI), `backend/app/modules/scorecard/services/normalizers/indicators.py:71` (SPI normalization).
  - Note: unlike CV (row #18 SUSPICIOUS — `budget_variance` clamps to ≥0 and loses the under-budget signal), the schedule equivalent SPI does NOT clamp. SPI > 1 = ahead, SPI < 1 = behind; the direction is preserved as a ratio. So the absence of an absolute signed SV is acceptable: the unitless ratio carries the same schedule-health signal currency-free and is what the scoring system already consumes.
  - If a reporting need surfaces (e.g. "how many euros of work are we behind?"), add `sv = ev − budgetTotal × percentPlanned` to `calculateEVMValues` with null guard for missing `percent_planned`, inheriting the single-currency assumption from row #18.
  - Audited: 2026-05-15 (calc-audit row #19)

- **percent_completed is a manual progress percentage (not a burn ratio)** — `backend/app/modules/tracker/public.py:75-85` (`_get_latest_progress`), wired through `get_evm_from_tracker` and `refresh_tracker_evm` (`scorecard/public.py:57-103`).
  - Checkpoint premise was wrong (`hours_logged / hours_budget` is not the formula). `percent_completed` is the user-entered `ProgressReportDB.percentage` for the latest reporting period, divided by 100 on write, stored as `Decimal(5,4)` 0..1.
  - Contracts: DB CHECK `percentage >= 0 AND percentage <= 1` + Pydantic `Field(ge=0, le=100)` on input. Cap enforced at both ends; >100 → 422; >1 cannot be stored. Consumer `EVMData.percent_completed` declares `ge=0, le=1` — unit matches.
  - Estimated-reports flag does NOT apply here: `percent_completed` comes from `progress_reports`, an independent table from `reports`/`report_parts`. The `estimated` filter only governs `cost_to_date` aggregation (correctly applied via `ReportDB.estimated.is_(False)`).
  - Edge case worth flagging (not a bug, more like a UX gap): a stale latest progress (project paused N months) keeps EV pinned while `percent_planned` advances linearly with `date.today()` → SPI drifts artificially low. No "must be from current period" guard. A "progress report is N months old" banner on EVMSection would close this.
  - Latent: `delete_project_metrics` does not wipe cached EVM if progress reports are deleted; stale `percent_completed` can linger on MetricsDB rows. Same family as cache invalidation findings in row #16.
  - Tests today: many tests seed `MetricsDB.percent_completed` directly, but **no test exercises `_get_latest_progress` or the tracker→scorecard propagation**. Suggested: `test_get_latest_progress_picks_latest_period`, `test_get_latest_progress_unit_is_ratio` (0.75 ≠ 75), `test_refresh_tracker_evm_propagates_percent_completed`.
  - Audited: 2026-05-15 (calc-audit row #22)

- **percent_planned (time-based interpolation)** — `backend/app/modules/tracker/public.py:88-101` (`_calculate_expected_progress`), call site at `public.py:42` inside `get_evm_from_tracker`.
  - Formula: `percent_planned = clamp((today - start_date).days / (end_date - start_date).days, 0.0, 1.0)`. Both date columns are `date` (timezone-less); `date.today()` uses server local time.
  - Edge cases handled: None for either date → None; `end == start` (zero-duration) → None via `total_days <= 0` guard; `end < start` blocked at DB by CHECK constraint + Pydantic validator + this guard; `today < start` clamped to 0.0; `today > end` clamped to 1.0.
  - Latent (not bugs):
    - Server-local timezone causes ±1 day drift around midnight for projects elsewhere. Coarse daily granularity makes this harmless.
    - Project marked `FINISHED` with `end_date` in the future: `percent_planned` keeps growing toward 1.0 even when work is done. Semantic gap (the project is "done", so planned vs completed makes less sense), not a calc bug — could short-circuit to 1.0 when status is FINISHED.
  - Tests today: **none** — no test imports `_calculate_expected_progress` or exercises `get_evm_from_tracker` with start/end inputs. All `percent_planned` mentions in tests pre-seed a Decimal into MetricsDB rather than deriving it.
  - Suggested: `test_planned_none_when_dates_missing`, `test_planned_zero_before_start`, `test_planned_one_after_end`, `test_planned_midpoint` (~0.5), `test_planned_exact_end` (=1.0).
  - Audited: 2026-05-15 (calc-audit row #23)

- **`estimated=true` flag exclusion** — `backend/app/modules/tracker/models/report.py:40` (Boolean, default=True, per-report not per-part).
  - Verified consumers (each behavior consistent with CLAUDE rule "estimated flag only affects burn"):
    - `aggregation_service._valid_parts_filter:36` (burn/cost summary/batch/FA-user/FA-only) → **excludes** estimated. ✓
    - `tracker.public._get_total_cost:58` (feeds scorecard EVM `cost_to_date` → SPI/CPI/budget_variance) → **excludes** estimated. ✓
    - `worker/report_confirmation_reminder.py:44` (DM reminder picks users without confirmed report) → uses `estimated.is_(False)` correctly. ✓
    - `aggregation_service.get_project_report_parts:213` (list view) → **includes**; surfaces `estimated` so UI can render badge. ✓
    - `core/services/capacity_insights.py:116/225/328/569/652` (insights, FA detail, user detail, allocation views) → **includes** estimated. Matches CLAUDE rule (capacity reflects intended/in-progress allocation). ✓
    - `api/moods.py:88/147` (mood distribution + trend) → **includes** all reports. Mood is captured on Confirm (write-once), so estimated reports have mood=null anyway; the `total_reports` denominator counts all reports.
    - `cost_service.apply_cost_and_days:54` → reads ReportDB only for user/period resolution; estimated flag irrelevant.
  - Default for new reports: `estimated=True`. Confirm requires parts summing to 100% (`reports.py:190`); Reopen unrestricted.
  - Latent observations (not calc bugs):
    - Moods denominator includes estimated reports: a period with many estimated submissions makes "response rate" misleading. Likely intentional but undocumented.
    - Mood on Reopen: if a user confirms (writes mood) then Reopens, the old mood persists in DB. CLAUDE says "write-once per confirm cycle" but there's no DB-level reset on reopen — a re-Confirm would silently keep the original mood.
  - Tests today cover: `test_cost_summary_excludes_estimated` (burn), `TestConfirmValidation` (write toggle), `test_create_with_estimated` (schema default), reminder-worker tests.
  - Suggested additions: `test_evm_cost_to_date_excludes_estimated` (direct path through scorecard public, no test today), `test_aggregation_fa_user_excludes_estimated` (FA breakdowns), `test_get_project_report_parts_includes_estimated_with_flag` (list view contract), `test_reopen_preserves_or_clears_mood` (pin the mood-on-reopen behavior).
  - Audited: 2026-05-15 (calc-audit row #29)

- **`_prepopulate_parts` — VHUB-124 fix verified** — `backend/app/modules/tracker/api/reports.py:40` (invoked at `:132` from `create_report`).
  - Filters applied (both required by VHUB-124):
    - `ReportPartDB.percentage > 0` (SQL `>` correctly drops both `0` and `NULL`, since `NULL > 0` is NULL/false).
    - `ProjectDB.status != ProjectStatus.FINISHED`.
    - Implicit: user_id match + immediately-previous reporting period (LIMIT 1).
  - New parts inserted as skeletons: `percentage=None, cost=None, days=None`. Values are NOT carried — only the row presence.
  - Edge cases handled: no previous period (first-ever) → 0 parts; user had no prior report → 0 parts; FINISHED project at create-time → excluded; percentage=0 or NULL → excluded; concurrent project-finish flips self-heal next period.
  - Latent observations (intentional / undocumented):
    - `ProjectStatus.PROPOSAL` is NOT filtered — a proposal-status project carries forward. Probably fine (target was finished), but if a project regresses LIVE → PROPOSAL it still seeds. Pin with a test if the contract matters.
    - Only looks at the immediately previous period (`LIMIT 1`). A user who skipped a month gets nothing pre-populated — does NOT walk further back. Likely intentional.
    - `ProjectStatus` enum has only PROPOSAL / LIVE / FINISHED — no `cancelled` value, so the "skip cancelled too" angle is moot.
  - Tests today (`test_reports.py::TestPrepopulateParts`): `test_skips_finished_projects` and `test_skips_zero_or_null_percentage_parts` both pin the VHUB-124 filters.
  - Suggested low-priority additions: `test_user_skipped_a_month_gets_empty_report`, `test_proposal_status_is_carried` (lock current behavior), `test_other_users_prev_report_not_used`, `test_prepopulate_strips_values` (assert all three fields are None).
  - Audited: 2026-05-15 (calc-audit row #32)

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
