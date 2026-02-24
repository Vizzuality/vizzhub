# Security Audit Report: ISO Module

**Audit Date**: 2026-02-24  
**Auditor**: Security Engineering (Automated)  
**Scope**: ISO Module -- backend API, services, models, schemas, frontend client  
**Module Path**: `backend/app/modules/iso/`  
**Frontend Path**: `frontend/src/services/api/iso.ts`, `frontend/src/hooks/useIso.ts`, `frontend/src/types/iso.ts`

---

## Executive Summary

**Overall Risk Level**: **Medium** -- The ISO module demonstrates solid security fundamentals (admin-only access, parameterized queries, OAuth state validation), but contains several medium-severity issues that should be addressed before the module handles sensitive organizational access data in production.

### Top 5 Critical Risks

1. **SEC-001**: OAuth tokens (access_token, refresh_token) stored in plaintext in the database
2. **SEC-002**: Missing rate limiting on most ISO endpoints (only export endpoints are rate-limited)
3. **SEC-003**: `captured_by` field not set during manual capture, leaving audit trail incomplete
4. **SEC-004**: In-memory OAuth state store does not survive process restarts and breaks in multi-worker deployments
5. **SEC-005**: No input validation (length, pattern) on Pydantic schema string fields

### Immediate Actions Required

- Encrypt OAuth tokens at rest in the database (SEC-001)
- Apply rate limiting to all mutation endpoints, especially `POST /capture` (SEC-002)
- Pass `current_user.user_id` to `captured_by` in `capture_snapshot` (SEC-003)
- Migrate OAuth state management to Redis or database (SEC-004)
- Add field-level validation constraints to all Pydantic schemas (SEC-005)

---

## Detailed Findings

### SEC-001: OAuth Tokens Stored in Plaintext

**Severity**: High  
**CWE**: CWE-312 (Cleartext Storage of Sensitive Information)  
**OWASP Top 10**: A02:2021 -- Cryptographic Failures

**Description**:  
Google Workspace OAuth access tokens and refresh tokens are stored as plaintext `Text` columns in the `oauth_tokens` table. The `OAuthTokenDB` model uses a plain `Text` column for `access_token` and `refresh_token` with no encryption layer.

**Impact**:  
An attacker who gains read access to the database (via SQL injection elsewhere in the application, backup exposure, or compromised database credentials) would immediately obtain valid Google Workspace OAuth tokens. These tokens grant read access to the entire organization's user directory, group memberships, and admin role assignments via the Google Admin Directory API.

**Exploitation Scenario**:
1. Attacker obtains database read access through any vector (backup, credential theft, SQL injection in another module).
2. Attacker queries `SELECT access_token, refresh_token FROM oauth_tokens WHERE provider = 'google_workspace'`.
3. Attacker uses the refresh token to generate new access tokens indefinitely.
4. Attacker enumerates all users, groups, admin roles, and group memberships in the Google Workspace domain.

**Evidence**:
- `backend/app/models/oauth.py`, lines 24-25:
  ```python
  access_token: Mapped[str] = mapped_column(Text, nullable=False)
  refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
  ```
- `backend/app/modules/iso/services/google_workspace_oauth.py`, lines 93-101: Tokens stored directly without encryption.
- Known gotcha in MEMORY.md: `bot_token_encrypted in slack_config is NOT actually encrypted -- stored in plaintext.` This is a pattern.

**Remediation**:
- Implement application-level encryption for tokens before storing them in the database using Fernet symmetric encryption or AWS KMS envelope encryption.
- Example:
  ```python
  from cryptography.fernet import Fernet

  class TokenEncryption:
      def __init__(self, key: str):
          self._fernet = Fernet(key.encode())

      def encrypt(self, plaintext: str) -> str:
          return self._fernet.encrypt(plaintext.encode()).decode()

      def decrypt(self, ciphertext: str) -> str:
          return self._fernet.decrypt(ciphertext.encode()).decode()
  ```
- Store the encryption key in environment variables or a secrets manager, not in the database.

**Attacker Profile**: Intermediate (requires database access but not application-level compromise)

---

### SEC-002: Missing Rate Limiting on Mutation and Read Endpoints

**Severity**: Medium  
**CWE**: CWE-770 (Allocation of Resources Without Limits or Throttling)  
**OWASP Top 10**: A04:2021 -- Insecure Design

**Description**:  
Rate limiting is applied only to the two export endpoints (`exports.py` lines 112, 151). All other ISO endpoints -- including the resource-intensive `POST /capture` endpoint that makes multiple paginated Google API calls, all CRUD operations, and the OAuth flow -- have no rate limits.

**Impact**:  
- **`POST /capture`**: An attacker (or compromised admin account) could repeatedly trigger Google Workspace API calls, potentially exhausting Google API quotas, causing denial of service for the Google Workspace integration, and filling the database with large snapshot records.
- **`DELETE /snapshots/{id}`**: Rapid deletion could destroy audit trail data.
- **`POST /reviews/{id}/sign` and `/unsign`**: Could be used to flip review state rapidly, undermining the integrity of the sign-off workflow.

**Exploitation Scenario**:
1. Attacker compromises an admin account.
2. Attacker scripts rapid `POST /iso/snapshots/capture` requests.
3. Google API quota is exhausted; legitimate capture operations fail.
4. Database fills with large JSON snapshot records (each containing full user/group data).

**Evidence**:
- `backend/app/modules/iso/api/snapshots.py`: No `@limiter.limit()` decorators on any endpoint.
- `backend/app/modules/iso/api/reviews.py`: No `@limiter.limit()` decorators on any endpoint.
- `backend/app/modules/iso/api/config.py`: No `@limiter.limit()` decorators on any endpoint.
- `backend/app/modules/iso/api/exports.py`, lines 112, 151: Only these two endpoints have rate limits.

**Remediation**:
```python
from app.api.deps import limiter

@router.post("/capture", ...)
@limiter.limit("5/hour")
async def capture_snapshot(request: Request, ...):
    ...

@router.delete("/{snapshot_id}", ...)
@limiter.limit("20/minute")
async def delete_snapshot(request: Request, ...):
    ...

@router.post("/{review_id}/sign", ...)
@limiter.limit("10/minute")
async def sign_review(request: Request, ...):
    ...
```

**Attacker Profile**: Script kiddie (automated requests against authenticated endpoints)

---

### SEC-003: Missing Audit Trail -- `captured_by` Not Set

**Severity**: Medium  
**CWE**: CWE-778 (Insufficient Logging)  
**OWASP Top 10**: A09:2021 -- Security Logging and Monitoring Failures

**Description**:  
The `capture_snapshot` endpoint creates a `GoogleWorkspaceCollector` and calls `collector.capture(run_mode="manual")` but never passes the authenticated user's ID as `captured_by`. The collector's `capture` method defaults `captured_by` to `None`.

**Impact**:  
The audit trail for ISO access snapshots is incomplete. In an ISO 27001 compliance context, every access review snapshot should record who initiated it. Without this, it is impossible to prove which administrator triggered a given data collection. This undermines the non-repudiation requirement of the access review process.

**Exploitation Scenario**:  
Not an exploitation scenario per se, but an audit/compliance gap. During an ISO 27001 audit, the auditor asks "Who initiated the access snapshot on 2026-02-15?" The `captured_by` field is NULL -- the organization cannot provide an answer.

**Evidence**:
- `backend/app/modules/iso/api/snapshots.py`, lines 41-43:
  ```python
  collector = GoogleWorkspaceCollector(db)
  try:
      snapshot = await collector.capture(run_mode="manual")
  ```
- `backend/app/modules/iso/services/collectors/google_workspace.py`, lines 142-146:
  ```python
  async def capture(
      self,
      captured_by: UUID | None = None,
      run_mode: str = "manual",
  ) -> AccessSnapshotDB:
  ```
  The `captured_by` parameter is never provided.

**Remediation**:
```python
@router.post("/capture", response_model=AccessSnapshotResponse, status_code=201)
async def capture_snapshot(
    current_user: AdminUser, db: DBSession
) -> AccessSnapshotDB:
    collector = GoogleWorkspaceCollector(db)
    try:
        snapshot = await collector.capture(
            captured_by=UUID(current_user.user_id),
            run_mode="manual",
        )
    except ValueError as e:
        ...
```

**Attacker Profile**: N/A (compliance gap, not an attack vector)

---

### SEC-004: In-Memory OAuth State Store Is Not Production-Safe

**Severity**: Medium  
**CWE**: CWE-613 (Insufficient Session Expiration) / CWE-384 (Session Fixation)  
**OWASP Top 10**: A07:2021 -- Identification and Authentication Failures

**Description**:  
The `OAuthStateManager` class uses an in-memory Python dictionary (`_states: dict[str, datetime] = {}`) to store OAuth CSRF state tokens. This is a class variable shared within a single process. In a multi-worker deployment (e.g., Gunicorn with multiple workers, or multiple containers behind a load balancer), the state token generated by one worker will not be available in another worker. Additionally, process restarts clear all pending states.

**Impact**:
- In multi-worker deployments, the OAuth callback may be routed to a different worker than the one that generated the state, causing legitimate OAuth flows to fail with "State expired or already used."
- Process restarts during an active OAuth flow will cause the flow to fail.
- The class-level dictionary is never cleaned up automatically in the normal request lifecycle (only via explicit `cleanup_expired()` calls), leading to potential memory growth.

**Evidence**:
- `backend/app/core/oauth_state.py`, lines 15-16:
  ```python
  class OAuthStateManager:
      _states: dict[str, datetime] = {}
  ```
- The `cleanup_expired()` method (line 56) is never called automatically.

**Remediation**:
- Migrate to Redis-backed state storage (Redis is already a dependency for the worker queue).
- Alternatively, rely solely on the session-based state validation (which already stores state in the session cookie via `SessionMiddleware`) and remove the in-memory store.
- Add periodic cleanup or TTL-based expiration.

```python
class OAuthStateManager:
    @staticmethod
    async def generate_state(redis: Redis) -> str:
        state = secrets.token_urlsafe(32)
        await redis.setex(f"oauth_state:{state}", 600, "1")  # 10 min TTL
        return state

    @staticmethod
    async def validate_state(state: str, redis: Redis) -> bool:
        result = await redis.getdel(f"oauth_state:{state}")
        return result is not None
```

**Attacker Profile**: N/A (reliability/architecture issue, but relevant to security posture)

---

### SEC-005: Missing Input Validation on Pydantic Schema Fields

**Severity**: Medium  
**CWE**: CWE-20 (Improper Input Validation)  
**OWASP Top 10**: A03:2021 -- Injection

**Description**:  
The Pydantic schemas (`AccessReviewUpdate`, `AccessReviewActionUpdate`, `SignReviewRequest`, `ActionDecision`) define string fields without any length constraints, pattern validation, or sanitization. The `notes` field, `justification` field, and `scope` field accept arbitrary-length strings.

**Impact**:
- **Denial of Service**: An attacker could submit megabytes of data in the `notes` or `justification` fields, consuming database storage and memory.
- **Storage Exhaustion**: Unbounded `Text` columns could grow to fill the database disk.
- **Log Injection**: Unconstrained strings could contain newlines or ANSI escape sequences that corrupt log output.

**Evidence**:
- `backend/app/modules/iso/schemas.py`, lines 78-80:
  ```python
  class AccessReviewUpdate(BaseModel):
      notes: str | None = None
      reviewer_id: UUID | None = None
  ```
  No `max_length`, `min_length`, or `Field()` constraints.
- `backend/app/modules/iso/schemas.py`, lines 102-106:
  ```python
  class AccessReviewActionUpdate(BaseModel):
      action_taken: ActionTaken | None = None
      justification: str | None = None
      approved_by: UUID | None = None
      exception_until: date | None = None
  ```
  No length constraints on `justification`.

**Remediation**:
```python
from pydantic import BaseModel, Field

class AccessReviewUpdate(BaseModel):
    notes: str | None = Field(None, max_length=10000)
    reviewer_id: UUID | None = None

class AccessReviewActionUpdate(BaseModel):
    action_taken: ActionTaken | None = None
    justification: str | None = Field(None, max_length=5000)
    approved_by: UUID | None = None
    exception_until: date | None = None

class ActionDecision(BaseModel):
    action_id: UUID
    action_taken: ActionTaken
    justification: str | None = Field(None, max_length=5000)
    exception_until: date | None = None
```

**Attacker Profile**: Script kiddie (trivial to exploit with oversized payloads)

---

### SEC-006: `approved_by` Field Allows Client-Controlled User Impersonation

**Severity**: Medium  
**CWE**: CWE-639 (Authorization Bypass Through User-Controlled Key)  
**OWASP Top 10**: A01:2021 -- Broken Access Control

**Description**:  
The `AccessReviewActionUpdate` schema includes an `approved_by: UUID | None` field that is directly set on the database model via `setattr`. This allows any admin user to set `approved_by` to any arbitrary user UUID, effectively impersonating another user's approval. The server does not validate that `approved_by` matches the authenticated user.

**Impact**:  
An admin could forge approval records, making it appear that a specific person approved an access review action when they did not. This undermines the integrity of the access review audit trail, which is critical for ISO 27001 compliance.

**Evidence**:
- `backend/app/modules/iso/schemas.py`, lines 102-106:
  ```python
  class AccessReviewActionUpdate(BaseModel):
      action_taken: ActionTaken | None = None
      justification: str | None = None
      approved_by: UUID | None = None
      exception_until: date | None = None
  ```
- `backend/app/modules/iso/api/reviews.py`, lines 118-122:
  ```python
  updates = body.model_dump(exclude_unset=True)
  for field, value in updates.items():
      if isinstance(value, Enum):
          value = value.value
      setattr(action, field, value)
  ```

**Remediation**:
- Remove `approved_by` from the update schema and set it server-side from the authenticated user.
```python
class AccessReviewActionUpdate(BaseModel):
    action_taken: ActionTaken | None = None
    justification: str | None = None
    exception_until: date | None = None
    # approved_by removed -- set server-side

# In the endpoint:
updates = body.model_dump(exclude_unset=True)
if updates:
    updates["approved_by"] = UUID(current_user.user_id)
for field, value in updates.items():
    ...
```

**Attacker Profile**: Intermediate (requires admin access but allows impersonation)

---

### SEC-007: Unvalidated `domain` Parameter in OAuth Flow

**Severity**: Medium  
**CWE**: CWE-20 (Improper Input Validation)  
**OWASP Top 10**: A03:2021 -- Injection

**Description**:  
The `domain` query parameter in the `authorize_google_workspace` endpoint is accepted as a bare `str` without any validation. It is used to construct the `hd` and `login_hint` parameters in the Google OAuth URL and is stored in the session. While Google's OAuth endpoint would reject obviously invalid values, a malicious domain value could be stored in the session and later used as the `site_url` in the `OAuthTokenDB` record, and also used as the `domain` field in `source_metadata` and for external member detection in the diff engine.

**Impact**:
- Misleading domain information in snapshot metadata and exports.
- The `login_hint` parameter is constructed as `admin@{domain}` -- an attacker could potentially use this for social engineering by setting a misleading `login_hint`.
- The domain is used for external member detection: `not email.endswith(f"@{domain}")`. A crafted domain value could cause false positives/negatives in external member detection.

**Evidence**:
- `backend/app/modules/iso/api/config.py`, line 31:
  ```python
  domain: str = Query(..., description="Google Workspace domain"),
  ```
- `backend/app/modules/iso/services/google_workspace_oauth.py`, lines 60-61:
  ```python
  params["hd"] = domain
  params["login_hint"] = f"admin@{domain}"
  ```

**Remediation**:
```python
import re

DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$")

@router.get("/google-workspace/authorize")
async def authorize_google_workspace(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    domain: str = Query(..., min_length=3, max_length=253, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
) -> RedirectResponse:
    ...
```

**Attacker Profile**: Intermediate (requires admin access)

---

### SEC-008: Unvalidated `status` and `provider` Query Parameters

**Severity**: Low  
**CWE**: CWE-20 (Improper Input Validation)  
**OWASP Top 10**: A03:2021 -- Injection

**Description**:  
The `list_reviews` endpoint accepts a `status: str | None` query parameter and the `list_snapshots` endpoint accepts a `provider: str | None` parameter. These are used directly in SQLAlchemy `where()` clauses. While SQLAlchemy uses parameterized queries (preventing SQL injection), the values are not validated against the known enum values (`ReviewStatus` for status, known provider names for provider). This means arbitrary strings can be queried, which is poor API hygiene.

**Impact**:  
Minimal direct security impact (SQLAlchemy parameterized queries prevent injection). However, it allows information probing -- an attacker could enumerate whether certain status/provider values exist by observing response patterns.

**Evidence**:
- `backend/app/modules/iso/api/reviews.py`, lines 36-37, 43-44:
  ```python
  status: str | None = None,
  ...
  if status:
      query = query.where(AccessReviewDB.status == status)
  ```
- `backend/app/modules/iso/api/snapshots.py`, lines 91, 105-107:
  ```python
  provider: str | None = None,
  ...
  if provider:
      query = query.where(AccessSnapshotDB.provider == provider)
  ```

**Remediation**:
```python
from app.modules.iso.schemas import ReviewStatus

@router.get("")
async def list_reviews(
    ...
    status: ReviewStatus | None = None,
    ...
):
```
Using the enum directly in the parameter type will make FastAPI validate it automatically and return a 422 for invalid values.

**Attacker Profile**: Script kiddie

---

### SEC-009: No Pagination Limit on Google Workspace API Pagination

**Severity**: Low  
**CWE**: CWE-400 (Uncontrolled Resource Consumption)  
**OWASP Top 10**: A04:2021 -- Insecure Design

**Description**:  
The `_paginate` method in `GoogleWorkspaceCollector` uses an unbounded `while True` loop to paginate through Google Workspace API results. For very large organizations, this could fetch millions of records, consuming significant memory and time. There is no upper bound on the number of pages or total items fetched.

**Impact**:
- Memory exhaustion on the application server for very large Google Workspace domains.
- Long-running HTTP request that could time out, leaving partial state.
- The entire fetched dataset is stored as a single JSONB column, potentially creating very large database rows.

**Evidence**:
- `backend/app/modules/iso/services/collectors/google_workspace.py`, lines 30-44:
  ```python
  async def _paginate(
      self, path: str, key: str, params: dict[str, Any] | None = None
  ) -> list[dict[str, Any]]:
      params = dict(params) if params else {}
      items: list[dict[str, Any]] = []
      while True:
          response = await self._client.get(path, params=params)
          response.raise_for_status()
          data = response.json()
          items.extend(data.get(key, []))
          page_token = data.get("nextPageToken")
          if not page_token:
              break
          params["pageToken"] = page_token
      return items
  ```

**Remediation**:
```python
MAX_PAGES = 100
MAX_ITEMS = 50000

async def _paginate(
    self, path: str, key: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    params = dict(params) if params else {}
    items: list[dict[str, Any]] = []
    page_count = 0
    while True:
        page_count += 1
        if page_count > MAX_PAGES:
            logger.warning("Pagination limit reached for %s", path)
            break
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        data = response.json()
        items.extend(data.get(key, []))
        if len(items) > MAX_ITEMS:
            logger.warning("Item limit reached for %s", path)
            break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        params["pageToken"] = page_token
    return items
```

**Attacker Profile**: N/A (operational risk, not direct attack vector)

---

### SEC-010: Missing Foreign Key Cascade Deletes on ISO Models

**Severity**: Low  
**CWE**: CWE-404 (Improper Resource Shutdown or Release)  
**OWASP Top 10**: N/A (Data Integrity)

**Description**:  
The ISO module's foreign key relationships (`AccessReviewDB.snapshot_id -> access_snapshots.id`, `AccessReviewActionDB.review_id -> access_reviews.id`) do not specify `ondelete="CASCADE"`. The `delete_snapshot` endpoint manually handles cascading deletes, but this is error-prone and could be bypassed if records are deleted through other code paths (database admin tools, migrations, other endpoints).

**Impact**:  
Orphaned review or action records if snapshots or reviews are deleted through non-API paths. This is consistent with a known project gotcha: `metrics FK to projects has NO ondelete="CASCADE"`.

**Evidence**:
- `backend/app/modules/iso/models/access_review.py`, lines 18-21:
  ```python
  snapshot_id: Mapped[UUID] = mapped_column(
      PG_UUID(as_uuid=True),
      ForeignKey("access_snapshots.id"),
      nullable=False,
  )
  ```
  No `ondelete="CASCADE"`.
- `backend/app/modules/iso/models/access_review_action.py`, lines 17-20: Same pattern.
- Manual cascade in `backend/app/modules/iso/api/snapshots.py`, lines 168-174.

**Remediation**:
```python
snapshot_id: Mapped[UUID] = mapped_column(
    PG_UUID(as_uuid=True),
    ForeignKey("access_snapshots.id", ondelete="CASCADE"),
    nullable=False,
)
```

**Attacker Profile**: N/A (data integrity issue)

---

### SEC-011: `ValueError` Exception Leaks Internal Details via `str(e)`

**Severity**: Low  
**CWE**: CWE-209 (Generation of Error Message Containing Sensitive Information)  
**OWASP Top 10**: A04:2021 -- Insecure Design

**Description**:  
In the `capture_snapshot` endpoint, `ValueError` exceptions are caught and their message is passed directly to the HTTP response via `str(e)`. If the collector code raises a `ValueError` with internal details (e.g., database connection strings, token fragments), these would be exposed to the client.

**Impact**:  
Currently the only `ValueError` messages are "Google Workspace not connected" and "Google Workspace domain not configured", which are safe. However, this pattern is fragile -- any future change to the collector that raises `ValueError` with sensitive context would leak that information.

**Evidence**:
- `backend/app/modules/iso/api/snapshots.py`, lines 44-45:
  ```python
  except ValueError as e:
      raise HTTPException(status_code=400, detail=str(e)) from e
  ```

**Remediation**:
```python
SAFE_VALUE_ERRORS = {
    "Google Workspace not connected",
    "Google Workspace domain not configured",
}

except ValueError as e:
    msg = str(e)
    if msg not in SAFE_VALUE_ERRORS:
        logger.error("Unexpected ValueError in capture: %s", msg)
        msg = "Snapshot capture failed"
    raise HTTPException(status_code=400, detail=msg) from e
```

**Attacker Profile**: Script kiddie (error-based information disclosure)

---

### SEC-012: Session Middleware Conditional on `session_secret_key`

**Severity**: Low  
**CWE**: CWE-311 (Missing Encryption of Sensitive Data)  
**OWASP Top 10**: A05:2021 -- Security Misconfiguration

**Description**:  
The `SessionMiddleware` is only added when `settings.session_secret_key` is set. If this environment variable is missing in a deployment, the session middleware will not be active, and the OAuth flow endpoints that use `request.session` will fail with an `AttributeError` or return empty values, potentially allowing OAuth state bypass.

**Impact**:  
If `session_secret_key` is not configured, the OAuth state validation in `google_workspace_callback` would fail. The `request.session.get("oauth_state")` call would either error or return `None`, which would be caught by the `if not session_state` check. However, the `session_secret_key` config has a default of `""` (empty string), which is falsy, meaning the middleware would not be added by default.

**Evidence**:
- `backend/app/main.py`, lines 112-117:
  ```python
  if settings.session_secret_key:
      app.add_middleware(
          SessionMiddleware,
          secret_key=settings.session_secret_key,
          ...
      )
  ```
- `backend/app/config.py`, line 18:
  ```python
  session_secret_key: str = ""
  ```

**Remediation**:
- Either make `session_secret_key` a required configuration value (raise an error if not set when ISO module is enabled), or generate a random session key at startup if not provided.
- Consider adding a startup check that validates the session middleware is active when the ISO module routes are registered.

**Attacker Profile**: N/A (misconfiguration risk)

---

### SEC-013: Unsign Review Endpoint Does Not Log the Unsigning User

**Severity**: Low  
**CWE**: CWE-778 (Insufficient Logging)  
**OWASP Top 10**: A09:2021 -- Security Logging and Monitoring Failures

**Description**:  
The `unsign_review` endpoint clears `signed_by` and `signed_at` but does not log who performed the unsigning action. While `current_user` is required for authentication, the identity of the person who reversed a signed review is not recorded anywhere in the database or audit log.

**Impact**:  
For ISO 27001 compliance, every state change in the access review workflow should be attributable. An admin could unsign a previously signed review, modify it, and re-sign it without any record of who performed the unsigning.

**Evidence**:
- `backend/app/modules/iso/api/reviews.py`, lines 192-207:
  ```python
  @router.post("/{review_id}/unsign", response_model=AccessReviewResponse)
  async def unsign_review(
      review_id: UUID, current_user: AdminUser, db: DBSession
  ) -> AccessReviewDB:
      review = await get_review_or_404(db, review_id)
      if review.status != ReviewStatus.SIGNED:
          raise HTTPException(status_code=409, detail="Review is not signed")
      review.status = ReviewStatus.DRAFT
      review.signed_at = None
      review.signed_by = None
      await db.flush()
      await db.refresh(review)
      return review
  ```

**Remediation**:
- Add an audit log entry recording who unsigned the review and when.
- Consider adding a `status_history` JSONB column or a separate audit log table.
```python
logger.info(
    "Review %s unsigned by user %s (was signed by %s at %s)",
    review_id,
    current_user.user_id,
    review.signed_by,
    review.signed_at,
)
```

**Attacker Profile**: N/A (compliance gap)

---

### SEC-014: Export Filename Constructed from User-Influenced Date Values

**Severity**: Low  
**CWE**: CWE-116 (Improper Encoding or Escaping of Output)  
**OWASP Top 10**: N/A

**Description**:  
The export endpoint constructs filenames using `from_date` and `to_date` parameters. While these are validated via `date.fromisoformat()`, the `Content-Disposition` header uses an f-string to insert dates. The `date.fromisoformat()` validation ensures only valid date strings pass through, so the actual risk is minimal. However, the pattern of using user input in HTTP headers should be flagged for awareness.

**Impact**:  
Minimal. The `date.fromisoformat()` validation ensures only strings like `2026-02-24` pass through, which cannot contain header injection characters. The risk would only materialize if the date parsing were loosened in the future.

**Evidence**:
- `backend/app/modules/iso/api/exports.py`, lines 142-146:
  ```python
  filename = f"iso_access_review_{start}_{end}.xlsx"
  return Response(
      content=output.getvalue(),
      media_type=XLSX_MEDIA_TYPE,
      headers={"Content-Disposition": f'attachment; filename="{filename}"'},
  )
  ```

**Remediation**:
- Current implementation is safe due to date validation. For defense-in-depth, sanitize the filename:
```python
import re

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-.]', '_', name)

filename = sanitize_filename(f"iso_access_review_{start}_{end}.xlsx")
```

**Attacker Profile**: N/A (currently safe, noted for future awareness)

---

## Positive Security Observations

The following security practices in the ISO module are commendable:

1. **Consistent Admin Authorization**: Every single endpoint uses the `AdminUser` dependency, which enforces the `admin` role via JWT token validation. No endpoints are accidentally exposed to non-admin users.

2. **Parameterized SQL Queries**: All database queries use SQLAlchemy's ORM and parameterized queries. No raw SQL or string interpolation is used in query construction. This effectively prevents SQL injection.

3. **UUID Path Parameters**: All path parameters (`snapshot_id`, `review_id`, `action_id`) use the `UUID` type, which FastAPI validates automatically. This prevents path traversal and IDOR attacks using non-UUID values.

4. **OAuth CSRF Protection**: The OAuth flow uses a dual-layer state validation (session-stored state + `OAuthStateManager` class), which is a defense-in-depth approach. The state token is cryptographically generated via `secrets.token_urlsafe(32)`.

5. **Signed Review Immutability**: The code correctly prevents modifications to signed reviews (HTTP 409), maintaining the integrity of the sign-off workflow.

6. **Action-Review Scoping**: The `update_action` endpoint validates that the action belongs to the specified review (`AccessReviewActionDB.review_id == review_id`), preventing cross-review action manipulation.

7. **No Token Exposure in Responses**: The `get_status` endpoint only returns `connected` and `domain` -- never the actual tokens. The `OAuthToken` Pydantic schema also excludes `access_token` and `refresh_token`.

8. **Proper Error Handling for External APIs**: Google Workspace API errors are caught (`httpx.HTTPStatusError`, `httpx.RequestError`) and converted to generic 502 responses without leaking Google API error details.

9. **Export Rate Limiting**: The export endpoints, which are the most resource-intensive read operations, are properly rate-limited at 10/minute.

10. **HTTPS-Only Session Cookies in Production**: The `SessionMiddleware` is configured with `https_only=not settings.debug`, ensuring session cookies are secure in production.

---

## Secure Architecture Recommendations

### 1. Token Encryption at Rest
Implement application-level encryption for all OAuth tokens using a dedicated encryption service. Use AWS KMS or a similar key management service for key rotation.

### 2. Audit Log Table
Create a dedicated `iso_audit_log` table to record all state-changing operations:
- Snapshot captures (who, when)
- Review status changes (who changed what, from what state to what state)
- Review unsigned events
- Action decisions made

### 3. Background Job for Capture
Move the Google Workspace data collection to a background job (using the existing ARQ worker) to avoid long-running HTTP requests and provide better resilience against timeouts.

### 4. Data Retention Policy
Implement a data retention policy for snapshots. Organizational user/group data is sensitive -- old snapshots should be retained only as long as needed for compliance (typically 3-7 years for ISO 27001) and then securely deleted.

### 5. Row-Level Security Considerations
Currently all admins can see all snapshots and reviews. If the organization scales to have multiple Google Workspace domains or tenant-level isolation is needed, consider adding org-scoped access controls.

---

## DevSecOps Pipeline Hardening

### SAST Integration
- Run `bandit` on the Python codebase to catch common security issues.
- Run `semgrep` with OWASP rules for Python/FastAPI.
- Add `eslint-plugin-security` for the frontend TypeScript code.

### Dependency Scanning
- Integrate `pip-audit` or `safety` for Python dependency vulnerability scanning.
- Run `npm audit` in CI for frontend dependencies.
- Consider Dependabot or Renovate for automated dependency updates.

### Secrets Detection
- Add `gitleaks` or `trufflehog` to the CI pipeline to prevent accidental secret commits.
- Ensure `.env` files remain in `.gitignore` (currently they are).

---

## Compliance Mapping

### ISO 27001 Controls

| Finding | ISO 27001 Control | Gap |
|---------|-------------------|-----|
| SEC-001 | A.10.1.1 (Cryptographic controls) | Tokens not encrypted at rest |
| SEC-003 | A.12.4.1 (Event logging) | Incomplete audit trail for capture operations |
| SEC-006 | A.9.2.5 (Review of user access rights) | Approver identity can be forged |
| SEC-013 | A.12.4.1 (Event logging) | Unsign action not logged |

### SOC2 Trust Services Criteria

| Finding | SOC2 Criteria | Gap |
|---------|---------------|-----|
| SEC-001 | CC6.1 (Logical and physical access controls) | Sensitive credentials not encrypted |
| SEC-003 | CC7.2 (Monitoring of system components) | Missing actor attribution in audit trail |
| SEC-004 | CC6.6 (Logical access security measures) | OAuth state management not production-ready |

---

## Summary of Findings by Severity

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| Critical | 0 | -- |
| High | 1 | SEC-001 |
| Medium | 5 | SEC-002, SEC-003, SEC-004, SEC-005, SEC-006, SEC-007 |
| Low | 7 | SEC-008, SEC-009, SEC-010, SEC-011, SEC-012, SEC-013, SEC-014 |

**Total Findings**: 14

The ISO module is well-architected from a security perspective, with consistent authentication enforcement and safe query construction. The most significant finding (SEC-001) relates to plaintext token storage, which should be remediated before handling production Google Workspace credentials. The remaining findings are primarily about hardening validation, improving audit trails, and ensuring production readiness of the OAuth flow.
