# Security Audit Report: `tracker` Branch

**Audit Date**: 2026-03-14
**Auditor**: Claude Opus 4.6 (Automated Security Review)
**Branch**: `tracker` (vs `main`)
**Scope**: All production-targeted code changes in the tracker branch

---

## Executive Summary

**Overall Risk Level**: **Medium** (with two High-severity findings requiring attention before production)

The tracker branch introduces a well-structured set of new endpoints, models, migrations, and worker cron jobs. The codebase shows good security practices overall: parameterized SQL queries, Pydantic validation on inputs, proper auth dependencies, and rate limiting. However, the audit identified several issues that should be addressed, two of which are High severity.

### Top 5 Critical Risks

1. **SEC-001 (High)**: Authorization gap in legacy `/api/scorecards` endpoints -- any authenticated user can create, update, and delete projects (no admin check).
2. **SEC-002 (High)**: Mass assignment via `setattr()` in PATCH endpoints -- `ProjectUpdate` schema accepts fields like `status` and `finished_at` that bypass intended workflow controls.
3. **SEC-003 (Medium)**: Hardcoded default database credentials in import scripts.
4. **SEC-004 (Medium)**: `ProjectUpdate` allows setting `program_id` to `None` via `exclude_unset` semantics ambiguity, potentially orphaning projects.
5. **SEC-005 (Low)**: Debug mode authentication bypass remains in codebase, safe behind `settings.debug` flag but warrants defense-in-depth hardening.

### Immediate Actions Required

- Fix authorization on legacy `projects.py` (scorecards) write endpoints to require `AdminUser`.
- Restrict PATCH `setattr` to an explicit allowlist of mutable fields.
- Remove default database credentials from scripts (require explicit `--target-db` or environment variable).

---

## Detailed Findings

### SEC-001: Missing Admin Authorization on Legacy Project Write Endpoints

**Severity**: High

**CWE**: CWE-862 (Missing Authorization)

**OWASP Top 10**: A01:2021 - Broken Access Control

**Description**:
The new `/api/projects` endpoints (in `projects_v2.py`) correctly require `AdminUser` for create, update, and delete operations. However, the legacy `/api/scorecards` endpoints (in `projects.py`) only require `CurrentUser` (any authenticated user) for `POST`, `PATCH`, `PUT`, and `DELETE` operations.

**Impact**:
Any authenticated user (including non-admin `user` role) can create, modify, or delete any project via the `/api/scorecards` endpoints. Since this platform handles financial data (budgets, invoices, billing rates), unauthorized project modification could lead to data integrity issues and operational disruption.

**Evidence**:
- `backend/app/core/api/projects_v2.py` lines 108-109: `admin: AdminUser` on `create_project`
- `backend/app/core/api/projects_v2.py` lines 159-160: `admin: AdminUser` on `replace_project`
- `backend/app/core/api/projects_v2.py` lines 192-193: `admin: AdminUser` on `update_project`
- `backend/app/core/api/projects_v2.py` lines 211-212: `admin: AdminUser` on `delete_project`

Compared to:
- `backend/app/core/api/projects.py` line 99: `current_user: CurrentUser` on `create_project`
- `backend/app/core/api/projects.py` line 129: `current_user: CurrentUser` on `update_project`
- `backend/app/core/api/projects.py` line 160: `current_user: CurrentUser` on `replace_project`
- `backend/app/core/api/projects.py` line 182: `current_user: CurrentUser` on `delete_project`

**Exploitation Scenario**:
1. Attacker authenticates as a regular user via Google SSO.
2. Attacker sends `DELETE /api/scorecards/{project_id}` to delete any project.
3. Associated metrics are cascade-deleted. No audit trail of who performed the action.

**Remediation**:
Change all write operations in `projects.py` to require `AdminUser`:

```python
# projects.py - create_project
async def create_project(
    request: Request, project: ProjectCreate, admin: AdminUser, db: DBSession
) -> Project:

# projects.py - update_project
async def update_project(
    request: Request, project_id: UUID, update: ProjectUpdate,
    admin: AdminUser, db: DBSession,
) -> Project:

# projects.py - replace_project, delete_project: same pattern
```

**Attacker Profile**: Script kiddie (authenticated internal user with basic API knowledge)

---

### SEC-002: Mass Assignment via `setattr()` in PATCH Endpoints

**Severity**: High

**CWE**: CWE-915 (Improperly Controlled Modification of Dynamically-Determined Object Attributes)

**OWASP Top 10**: A01:2021 - Broken Access Control / A08:2021 - Software and Data Integrity Failures

**Description**:
Both `projects.py` and `projects_v2.py` use `setattr(project, field, value)` to apply PATCH updates. The `ProjectUpdate` Pydantic model accepts `status`, `finished_at`, `has_scorecard`, `has_dependabot_alerts`, and `has_budget_alerts` fields. While Pydantic limits the field names to those declared in the schema (preventing true arbitrary attribute injection), the pattern is dangerous because:

1. The `ProjectUpdate` model has no cross-field validation (unlike `ProjectBase`). A user can set `status=finished` without providing `finished_at`, or set `finished_at` to an arbitrary date.
2. Feature flags (`has_scorecard`, `has_dependabot_alerts`, `has_budget_alerts`) can be toggled via PATCH, potentially disabling security monitoring for a project.
3. The `clear_finished_at` flag is a boolean that allows clearing the `finished_at` timestamp, enabling workflow bypass.

**Impact**:
An admin could bypass intended project lifecycle controls. More critically, if SEC-001 is not fixed, any authenticated user could toggle project feature flags off to suppress Dependabot alerts and budget monitoring.

**Evidence**:
- `backend/app/core/api/projects_v2.py` lines 197-203
- `backend/app/core/api/projects.py` lines 138-147

**Exploitation Scenario**:
1. User sends `PATCH /api/scorecards/{id}` with `{"has_dependabot_alerts": false, "has_budget_alerts": false}`.
2. The project silently stops receiving security vulnerability and budget overrun alerts.
3. Critical vulnerabilities go unnoticed in production.

**Remediation**:
Use an explicit allowlist pattern instead of blindly iterating `model_dump()`:

```python
PATCHABLE_FIELDS = {
    "name", "code", "program_id", "is_billable", "currency",
    "notes", "summary", "jira_project_key", "github_repo",
    "start_date", "end_date", "slack_channel_id",
}

# Feature flag fields that should require explicit admin intent
ADMIN_ONLY_FIELDS = {
    "status", "finished_at", "has_scorecard",
    "has_dependabot_alerts", "has_budget_alerts",
}

update_data = update.model_dump(exclude_unset=True)
allowed = PATCHABLE_FIELDS | ADMIN_ONLY_FIELDS  # admin already required
for field, value in update_data.items():
    if field not in allowed:
        continue
    # ... apply
```

Also add cross-field validation to `ProjectUpdate` for `status`/`finished_at` consistency.

**Attacker Profile**: Intermediate (authenticated user with API knowledge)

---

### SEC-003: Hardcoded Default Database Credentials in Scripts

**Severity**: Medium

**CWE**: CWE-798 (Use of Hard-coded Credentials)

**OWASP Top 10**: A07:2021 - Identification and Authentication Failures

**Description**:
Both `import_vizztracker.py` and `enable_production_scorecard.py` contain hardcoded default database connection strings with credentials:

```python
default="postgresql://scorecard:scorecard@localhost:5432/scorecard"
```

While these are development defaults and the scripts are CLI tools (not exposed via HTTP), they represent a credential hygiene issue. If these defaults are accidentally used in production or if the credentials match production values, it creates an unnecessary risk.

**Evidence**:
- `backend/scripts/import_vizztracker.py` lines 848-849
- `backend/scripts/enable_production_scorecard.py` lines 31-32

**Exploitation Scenario**:
1. Script is run on a production server without specifying `--target-db`.
2. If the production PostgreSQL accepts connections from localhost with these credentials, the script connects to the wrong database or an attacker who has read access to the repo knows production DB credentials.

**Remediation**:
Remove hardcoded defaults. Require the `--target-db` flag or read from `DATABASE_URL` environment variable:

```python
parser.add_argument(
    '--target-db',
    default=os.environ.get('DATABASE_URL'),
    required=not os.environ.get('DATABASE_URL'),
    help='Target database URL (or set DATABASE_URL env var)',
)
```

**Attacker Profile**: Intermediate (requires repo access + network position)

---

### SEC-004: `program_id` Nullable Ambiguity in ProjectUpdate

**Severity**: Medium

**CWE**: CWE-20 (Improper Input Validation)

**OWASP Top 10**: A03:2021 - Injection (data integrity)

**Description**:
In `ProjectUpdate`, the field `program_id: UUID | None = None` combined with `model_dump(exclude_unset=True)` creates ambiguity. If a client sends `{"program_id": null}`, Pydantic includes it in the dump (it was explicitly set), and `setattr(project, "program_id", None)` will clear the program association. However, if the client simply omits `program_id`, it is excluded. This is correct Pydantic behavior, but the same ambiguity applies to other fields like `notes`, `summary`, `code`, etc.

The real concern is that there is no validation that clearing `program_id` is intentional versus accidental. A malformed API call could silently disassociate a project from its program.

**Impact**:
Data integrity risk. Projects could lose their program association without explicit user intent, affecting reporting and organizational structure.

**Remediation**:
This is a design consideration rather than a vulnerability. Document the behavior and consider adding audit logging for field changes on sensitive fields. For `program_id` specifically, consider requiring a separate explicit action to disassociate.

**Attacker Profile**: Low (accidental misuse more likely than intentional attack)

---

### SEC-005: Debug Mode Authentication Bypass

**Severity**: Low (in current state -- properly gated behind `settings.debug`)

**CWE**: CWE-287 (Improper Authentication)

**OWASP Top 10**: A07:2021 - Identification and Authentication Failures

**Description**:
When `DEBUG=true`, the authentication system returns a mock admin user with both `user` and `admin` roles if no token is provided. This is correctly gated behind the `debug` flag, and the CORS validator rejects localhost origins when `debug=false`. However:

1. There is no runtime assertion that `DEBUG` is `false` in production.
2. If someone misconfigures `DEBUG=true` in production, all endpoints become accessible without authentication.
3. The mock user gets admin privileges, making the entire API fully open.

**Evidence**:
- `backend/app/core/auth.py` lines 96-104
- `backend/.env.example` line 34: `DEBUG=true`

**Remediation**:
Add a startup check that fails hard if `DEBUG=true` and the environment looks like production:

```python
# In lifespan function
if settings.debug and os.environ.get("DEPLOYMENT_ENV") == "production":
    raise RuntimeError("DEBUG=true is not allowed in production")
```

Or check for the presence of production indicators like a non-localhost `DATABASE_URL`.

**Attacker Profile**: N/A (misconfiguration risk, not direct attack)

---

### SEC-006: Missing Cascade Delete for Metrics FK

**Severity**: Medium

**CWE**: CWE-404 (Improper Resource Shutdown or Release)

**OWASP Top 10**: N/A (data integrity)

**Description**:
The delete endpoint in `projects_v2.py` manually deletes MetricsDB records before deleting the project (lines 245-246). This is because `metrics` FK to `projects` has no `ondelete="CASCADE"` (as noted in MEMORY.md). However, the new tracker module tables (budget_lines, invoices, reports, etc.) DO have `ondelete="CASCADE"`. This inconsistency means:

1. The delete endpoint checks for `report_parts` and `progress_reports` existence before deletion (lines 219-243), but cascade would handle tracker tables.
2. Other tables that might reference the project (e.g., `tracker_project_settings`, `non_staff_costs`, `budget_lines`) are cascaded, so the manual check is only for report integrity.
3. The delete endpoint does NOT check for or delete `links` (which CASCADE), scorecard `scores`, ISO snapshots, or other module data.

**Evidence**:
- `backend/app/core/api/projects_v2.py` lines 209-247

**Impact**:
Orphaned data if new modules add project references without CASCADE. The current code is correct for existing tables but fragile for future changes.

**Remediation**:
Add a migration to set `ondelete="CASCADE"` on the `metrics` FK. This would simplify the delete logic and reduce the risk of orphaned data:

```python
# Migration
op.drop_constraint("metrics_project_id_fkey", "metrics", type_="foreignkey")
op.create_foreign_key(
    "metrics_project_id_fkey", "metrics", "projects",
    ["project_id"], ["id"], ondelete="CASCADE"
)
```

**Attacker Profile**: N/A (code maintenance issue)

---

### SEC-007: Import Script Prints Database URLs to stdout

**Severity**: Low

**CWE**: CWE-532 (Insertion of Sensitive Information into Log File)

**OWASP Top 10**: A09:2021 - Security Logging and Monitoring Failures

**Description**:
The import script prints the full database connection URLs (which may contain credentials) to stdout:

```python
print(f"Legacy DB: {args.legacy_db}")
print(f"Target DB: {args.target_db}")
```

If run in CI/CD or with output logging, credentials would be captured in logs.

**Evidence**:
- `backend/scripts/import_vizztracker.py` lines 854-855

**Remediation**:
Mask credentials in output:

```python
from urllib.parse import urlparse

def mask_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(f":{parsed.password}@", ":****@")
    return url

print(f"Legacy DB: {mask_url(args.legacy_db)}")
print(f"Target DB: {mask_url(args.target_db)}")
```

**Attacker Profile**: Low (requires access to CI/CD logs)

---

### SEC-008: No Rate Limiting on Worker Cron Jobs

**Severity**: Low

**CWE**: CWE-770 (Allocation of Resources Without Limits or Throttling)

**OWASP Top 10**: N/A (operational)

**Description**:
The monthly scorecard capture cron and business alerts cron iterate over all eligible projects sequentially with a 5-second sleep between projects. While this is reasonable, there is no mechanism to limit the total number of external API calls (Jira, GitHub) per cron run. If the number of projects grows significantly, the cron could overwhelm external APIs and trigger rate limits.

Additionally, ARQ `max_tries=2` with `retry_jobs=True` means failed cron jobs will retry, potentially doubling the external API load.

**Evidence**:
- `backend/app/worker/settings.py` lines 66-67: `retry_jobs = True`, `max_tries = 2`
- `backend/app/worker/monthly_scorecard_capture.py` lines 68-106

**Remediation**:
Consider adding per-run caps and exponential backoff for external API calls. The 5-second sleep is a good start but should be configurable.

**Attacker Profile**: N/A (operational concern)

---

### SEC-009: Slack Alert Template Injection via Project Names

**Severity**: Low

**CWE**: CWE-74 (Improper Neutralization of Special Elements in Output)

**OWASP Top 10**: A03:2021 - Injection

**Description**:
The `AlertService.render_template()` uses simple string `{placeholder}` replacement. Project names are inserted directly into Slack messages. While Slack mrkdwn is not as dangerous as HTML (no script execution), a project name containing Slack formatting characters like `*`, `~`, `<`, `>` could alter message formatting or create misleading links.

For example, a project named `*Fake Alert* <https://evil.com|Click here>` would render as bold text with a clickable link in Slack.

**Evidence**:
- `backend/app/modules/scorecard/services/alert_service.py` lines 22-38
- Project names from `check_business_alerts.py` line 293: `"project_name": project.name`

**Impact**:
An admin who can name projects could craft project names that produce misleading Slack messages. Low impact since only admins can create/rename projects (assuming SEC-001 is fixed).

**Remediation**:
Sanitize project names in alert context by escaping Slack mrkdwn special characters:

```python
def escape_slack_mrkdwn(text: str) -> str:
    for char in ("&", "<", ">"):
        text = text.replace(char, f"&{'amp' if char == '&' else 'lt' if char == '<' else 'gt'};")
    return text
```

**Attacker Profile**: Low (requires admin access)

---

## Positive Security Observations

The following security practices are well-implemented and deserve recognition:

1. **Parameterized queries throughout**: All SQL queries use SQLAlchemy ORM or parameterized psycopg2 queries (`%s` placeholders). No SQL injection vectors found.

2. **LIKE clause escaping**: The `_escape_like()` function in both `projects.py` and `projects_v2.py` properly escapes `%`, `_`, and `\` characters before use in `ILIKE` clauses.

3. **Input validation via Pydantic**: All API endpoints use Pydantic models with field validators, max lengths, regex patterns, and cross-field validation (e.g., `end_date >= start_date`).

4. **UUID-based identifiers**: All entity IDs use UUIDs, preventing enumeration attacks.

5. **Rate limiting**: All endpoints have appropriate rate limits via `slowapi`.

6. **Security headers**: The `SecurityHeadersMiddleware` adds HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and other headers.

7. **CORS validation**: Production mode rejects localhost origins.

8. **httpOnly cookies**: JWT tokens are stored in httpOnly cookies with SameSite=Lax, preventing XSS-based token theft.

9. **Check constraints in migrations**: Database-level constraints enforce data integrity (percentage ranges, positive amounts, valid status enums).

10. **Proper FK cascades**: New tracker tables use appropriate CASCADE/RESTRICT/SET NULL strategies.

11. **Idempotent import script**: The data import script uses ON CONFLICT clauses and transaction management with rollback on failure.

12. **Swagger disabled in production**: `docs_url`, `redoc_url`, and `openapi_url` are `None` when `debug=false`.

---

## Secure Architecture Recommendations

### Cross-cutting Improvements

1. **Add audit logging for write operations**: All create/update/delete operations should log the authenticated user ID, action, and affected resource. This is absent from both old and new endpoints.

2. **Add field-level change tracking**: For sensitive fields (status, feature flags, financial data), log old and new values.

3. **Consider row-level security**: As the platform grows, consider project-scoped access controls (e.g., only project members can view project details).

4. **Add request ID middleware**: Generate a unique request ID per request for correlation in logs and error responses.

### Defense-in-Depth

1. **Database user separation**: Use separate DB users for the web application (limited DML) and migration runner (full DDL). The import script should use a dedicated DB user.

2. **Read-only replicas**: Route read-heavy endpoints (list, get) to a read replica to reduce load on the primary.

3. **Secret rotation**: Implement JWT secret key rotation with a grace period for old tokens.

---

## DevSecOps Pipeline Hardening

### Recommended Additions

1. **SAST**: Run `bandit` (Python) and `eslint-plugin-security` (TypeScript) in CI.
2. **Dependency scanning**: `pip-audit` for Python, `npm audit` for Node (already addressed in Dependabot).
3. **Container scanning**: If using Docker, add `trivy` or `grype` scanning.
4. **Secret detection**: Add `trufflehog` or `gitleaks` to pre-commit hooks to catch credentials before they reach the repo.
5. **Migration review gate**: Require manual review of any Alembic migration that modifies security-relevant tables (users, auth, permissions).

---

## Compliance Notes

### SOC2 Trust Services Criteria

- **CC6.1 (Logical and Physical Access Controls)**: SEC-001 must be fixed. Write operations need proper role enforcement.
- **CC6.3 (Authorized Access)**: SEC-002 should be addressed to prevent unintended attribute modification.
- **CC7.2 (Monitoring)**: Audit logging should be added for all state-changing operations.

### GDPR Considerations

- User email addresses are stored and used for authentication. The import script copies user data (email, name) from a legacy system. Ensure data processing agreements cover this data migration.
- The `UserDB` model stores `picture` (Google profile picture URL) -- ensure this is covered in the privacy policy.

---

## Summary Table

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| SEC-001 | Missing admin auth on legacy project endpoints | High | Must fix |
| SEC-002 | Mass assignment via setattr in PATCH | High | Must fix |
| SEC-003 | Hardcoded default DB credentials in scripts | Medium | Should fix |
| SEC-004 | program_id nullable ambiguity | Medium | Accept risk |
| SEC-005 | Debug mode auth bypass | Low | Harden |
| SEC-006 | Missing CASCADE on metrics FK | Medium | Should fix |
| SEC-007 | DB URLs printed to stdout | Low | Should fix |
| SEC-008 | No rate limiting on worker crons | Low | Accept risk |
| SEC-009 | Slack template injection via project names | Low | Should fix |

**Total findings**: 9 (2 High, 3 Medium, 4 Low)

---

*Report generated by automated security audit. Findings should be validated by the development team before remediation.*
