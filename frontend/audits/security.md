# Security Audit Report: JWT httpOnly Cookie Refactor

**Audit Date:** 2026-02-05
**Auditor:** Security Audit (Automated)
**Scope:** JWT storage migration from localStorage to httpOnly cookies
**Branch:** `dev`

---

## Executive Summary

**Overall Risk Level:** LOW (with caveats)

The JWT httpOnly cookie refactor has been implemented with strong security fundamentals. The migration from localStorage to httpOnly cookies eliminates the primary XSS-based token theft vector, which is a significant security improvement. The implementation follows OWASP best practices in most areas. However, several findings require attention before production deployment.

### Top 5 Risks (Prioritized)

1. **Missing `domain` attribute on cookie** -- could cause cookie scope issues or be overly permissive in certain deployment topologies (MEDIUM)
2. **Cookie `path` restriction to `/api` prevents frontend-initiated logout confirmation** -- but current implementation handles this correctly (INFO)
3. **Stale Login.tsx with hardcoded auth bypass link** ships to production builds (LOW)
4. **User profile data cached in localStorage without integrity verification** -- could be tampered for UI spoofing (LOW)
5. **No explicit CSRF token mechanism** -- relies on defense-in-depth (SameSite + JSON + CORS), which is acceptable per OWASP but worth documenting (INFO)

### Immediate Actions Required

- None are blocking for production deployment. All findings are LOW/MEDIUM/INFO severity.
- The refactor is well-executed and safe for production use.

---

## Detailed Findings

---

### Finding SEC-001

**Title:** Missing `domain` Attribute in Cookie Configuration

**Severity:** MEDIUM

**CWE:** CWE-1004 (Sensitive Cookie Without 'HttpOnly' Flag) -- tangentially related; CWE-614 (Sensitive Cookie in HTTPS Session Without 'Secure' Attribute) -- broad cookie security

**OWASP Top 10:** A05:2021 - Security Misconfiguration

**Description:**

The `get_cookie_settings()` function in `/Volumes/Work/Dev/project-score-card/backend/app/core/auth.py` (lines 24-33) does not explicitly set a `domain` attribute on the cookie. When `domain` is omitted, the cookie is scoped to the exact host that set it (no subdomain sharing), which is the default secure behavior per RFC 6265. However, this means the behavior is implicit rather than explicit.

In the production deployment architecture (ALB with path-based routing), the cookie is set by the backend (`backend:8000`) and forwarded through ALB to the client on the production domain. Since ALB forwards the response headers including `Set-Cookie`, and the browser associates the cookie with the request origin (the production domain), this works correctly.

**Impact:**

Minimal in current architecture. If the architecture ever changes to use separate subdomains for API and frontend (e.g., `api.example.com` and `app.example.com`), cookies would fail silently. The omission makes the cookie config fragile to architectural changes.

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/core/auth.py, lines 24-33
def get_cookie_settings() -> dict:
    """Return cookie parameters based on environment."""
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": not settings.debug,
        "samesite": "lax",
        "path": "/api",
        "max_age": settings.jwt_expire_hours * 3600,
        # No "domain" attribute
    }
```

**Remediation:**

This is acceptable as-is given the single-domain deployment. Document the assumption that the API and frontend share the same origin. If subdomain separation is ever introduced, add an explicit `domain` setting loaded from environment configuration.

**Attacker Profile:** N/A -- not directly exploitable

---

### Finding SEC-002

**Title:** Cookie `path` Scoped to `/api` -- Correct and Intentional

**Severity:** INFO

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The cookie `path` is set to `/api`, meaning the browser will only attach the cookie to requests whose URL path starts with `/api`. This is a good security practice as it minimizes the cookie's exposure surface -- it will not be sent with requests for static assets, frontend routes, or other non-API paths.

This is verified to work correctly with the frontend because:
- The axios client uses `baseURL: '/api'` (`/Volumes/Work/Dev/project-score-card/frontend/src/services/api/client.ts`, line 4)
- The Vite dev proxy forwards `/api` to the backend (`/Volumes/Work/Dev/project-score-card/frontend/vite.config.ts`, lines 31-36)
- In production, ALB routes `/api/*` to the backend target group (`/Volumes/Work/Dev/project-score-card/infrastructure/alb.tf`, listener rule)
- All frontend `fetch()` calls that need auth use paths starting with `/api` and include `credentials: 'include'`

**Evidence:**

The path restriction is properly aligned across all layers of the stack.

**Remediation:** None needed. This is a positive finding.

---

### Finding SEC-003

**Title:** CSRF Protection via Defense-in-Depth (SameSite + JSON Content-Type + CORS)

**Severity:** INFO

**CWE:** CWE-352 (Cross-Site Request Forgery)

**OWASP Top 10:** A01:2021 - Broken Access Control

**Description:**

The implementation does not use explicit CSRF tokens. Instead, it relies on a layered defense:

1. **SameSite=Lax**: The cookie uses `samesite="lax"`, which prevents the cookie from being sent on cross-origin POST requests initiated by third-party sites (forms, XHR from other domains). GET requests from cross-site navigation will include the cookie, but all state-changing operations use POST/PATCH/DELETE.

2. **JSON Content-Type**: All API requests send `Content-Type: application/json`. HTML forms cannot send JSON content type, and cross-origin `fetch`/XHR with non-simple content types trigger CORS preflight.

3. **CORS with explicit origins**: The CORS configuration uses explicit `allow_origins` (not wildcard) with `allow_credentials=True` (`/Volumes/Work/Dev/project-score-card/backend/app/main.py`, lines 100-106). This means the browser will reject cross-origin responses and block preflight for unauthorized origins.

**Analysis per OWASP CSRF Prevention Cheat Sheet:**

The combination of SameSite=Lax + CORS with specific origins + JSON Content-Type is considered a valid CSRF defense per OWASP guidance. SameSite=Lax alone prevents cross-origin POST requests from including the cookie. The JSON Content-Type requirement adds defense-in-depth since HTML forms cannot produce `application/json` requests.

**Limitation:** SameSite=Lax does allow the cookie on top-level GET navigations from external sites. If any GET endpoint has state-changing side effects, it would be vulnerable. Review confirms all state-changing endpoints use POST/PATCH/DELETE methods.

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/main.py, lines 100-106
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Explicit list, not "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```python
# /Volumes/Work/Dev/project-score-card/backend/app/config.py, lines 56-69
@field_validator("cors_origins")
@classmethod
def validate_cors_origins_production(cls, v: list[str], info: ValidationInfo) -> list[str]:
    """Validate CORS origins - reject localhost in production."""
    debug = info.data.get("debug", False)
    if not debug:
        for origin in v:
            if "localhost" in origin or "127.0.0.1" in origin:
                raise ValueError(...)
    return v
```

**Remediation:**

The current approach is acceptable per OWASP guidelines. For maximum protection, consider adding an explicit CSRF token (double-submit cookie pattern) for critical operations (user role changes, project deletion). However, this is a hardening measure, not a vulnerability fix.

**Attacker Profile:** Advanced (would need to find a same-site XSS vulnerability to bypass this protection)

---

### Finding SEC-004

**Title:** CORS Configuration Properly Prevents Wildcard with Credentials

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The CORS configuration correctly uses an explicit origin list rather than wildcard (`*`). Per the Fetch specification, `Access-Control-Allow-Origin: *` is incompatible with `Access-Control-Allow-Credentials: true`. FastAPI's CORSMiddleware correctly enforces this: when `allow_credentials=True`, it reflects the requesting origin only if it matches the allowed list.

Additionally, the production CORS validator (`validate_cors_origins_production` in `/Volumes/Work/Dev/project-score-card/backend/app/config.py`, lines 56-69) rejects localhost origins when `DEBUG=false`, preventing accidental development origins in production.

The production deployment sets: `CORS_ORIGINS=["https://${domain_name}"]` (`/Volumes/Work/Dev/project-score-card/infrastructure/templates/user_data.sh`, line 125).

**Evidence:** See code references above.

**Remediation:** None needed. This is well implemented.

---

### Finding SEC-005

**Title:** Token Resolution Order (Cookie-First, Header-Fallback) is Secure

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The `get_current_user()` function in `/Volumes/Work/Dev/project-score-card/backend/app/core/auth.py` (lines 93-154) reads the token from the httpOnly cookie first, then falls back to the `Authorization: Bearer` header.

This order is correct:
- **Cookie-first** ensures the browser-based frontend uses the httpOnly cookie (immune to XSS theft)
- **Header-fallback** allows non-browser clients (API scripts, the `generate_jwt_token.py` utility, CI/CD) to authenticate via Bearer tokens
- Both paths perform identical JWT validation (same secret, same algorithm, same claims checks)

The cookie always takes precedence, so an attacker cannot inject a malicious Bearer header to override a valid cookie in a browser context (browsers send cookies automatically; the frontend does not set Authorization headers).

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/core/auth.py, lines 105-108
token: str | None = request.cookies.get(COOKIE_NAME)
if not token and credentials is not None:
    token = credentials.credentials
```

**Remediation:** None needed. Test coverage confirms this behavior (`test_cookie_takes_precedence_over_header` in `/Volumes/Work/Dev/project-score-card/backend/tests/test_auth.py`, line 191).

---

### Finding SEC-006

**Title:** Login Response Does Not Leak JWT in Response Body

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The `google_auth()` endpoint in `/Volumes/Work/Dev/project-score-card/backend/app/api/auth.py` (lines 35-124) correctly:

1. Creates the JWT and sets it exclusively via `response.set_cookie()` (line 113)
2. Returns only the `AuthLoginResponse` model which contains `user: UserPublic` (line 115-116) -- no token field
3. The `AuthLoginResponse` Pydantic model (`/Volumes/Work/Dev/project-score-card/backend/app/api/auth.py`, lines 29-32) has no `access_token` or `token` field

The frontend `AuthLoginResponse` type (`/Volumes/Work/Dev/project-score-card/frontend/src/types/auth.ts`, lines 28-30) also confirms no token field:

```typescript
export interface AuthLoginResponse {
  user: UserPublic;
}
```

**Remediation:** None needed. The token never appears in the response body, eliminating the risk of JavaScript-accessible token leakage.

---

### Finding SEC-007

**Title:** Logout Correctly Clears Cookie with Matching Parameters

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The `logout()` endpoint in `/Volumes/Work/Dev/project-score-card/backend/app/api/auth.py` (lines 147-159) correctly clears the cookie by calling `response.delete_cookie()` with all the same parameters used to set it: `key`, `path`, `samesite`, `secure`, and `httponly`. This ensures the browser matches the deletion to the correct cookie.

Both operations use `get_cookie_settings()` as the source of truth, preventing parameter drift between set and delete operations.

The frontend logout handler (`/Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx`, lines 60-76) also properly clears the localStorage user cache after calling the logout endpoint, with a best-effort approach (clears local state even if the network request fails).

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/api/auth.py, lines 150-157
cookie_settings = get_cookie_settings()
response.delete_cookie(
    key=cookie_settings["key"],
    path=cookie_settings["path"],
    samesite=cookie_settings["samesite"],
    secure=cookie_settings["secure"],
    httponly=cookie_settings["httponly"],
)
```

**Remediation:** None needed.

---

### Finding SEC-008

**Title:** No Remaining `auth_token` or `TOKEN_STORAGE_KEY` References in Frontend Source

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

A comprehensive search of the frontend source directory (`/Volumes/Work/Dev/project-score-card/frontend/src/`) for patterns `auth_token`, `TOKEN_STORAGE_KEY`, `localStorage.*token`, and `token.*localStorage` returned zero matches. The old localStorage-based token storage has been completely removed.

The only localStorage usage remaining is:
- `auth_user` key in `AuthContext.tsx` and `client.ts` -- stores user profile info (name, email, role, picture) for UI display, not the JWT
- `projectsViewMode` in `Projects.tsx` -- UI preference
- `active_capture_job_*` in `HistoricalCaptureSection.tsx` -- background job tracking

None of these store sensitive authentication tokens.

**Evidence:** Grep search across `/Volumes/Work/Dev/project-score-card/frontend/src/` returned no matches for token-in-localStorage patterns.

**Remediation:** None needed. The cleanup is thorough.

---

### Finding SEC-009

**Title:** Frontend Properly Uses `credentials: 'include'` / `withCredentials: true`

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

All HTTP client paths in the frontend correctly include credentials:

1. **Axios client** (`/Volumes/Work/Dev/project-score-card/frontend/src/services/api/client.ts`, line 8): `withCredentials: true`
2. **AuthContext login** (`/Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx`, line 37): `credentials: 'include'`
3. **AuthContext logout** (`/Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx`, line 64): `credentials: 'include'`
4. **AuthContext validateSession** (`/Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx`, line 84): `credentials: 'include'`
5. **useUsers fetchWithAuth** (`/Volumes/Work/Dev/project-score-card/frontend/src/hooks/useUsers.ts`, line 17): `credentials: 'include'`

The `useUsers.ts` hook uses raw `fetch()` instead of the shared axios client but correctly includes `credentials: 'include'`.

**Remediation:** None needed. All HTTP paths include credentials correctly.

---

### Finding SEC-010

**Title:** Development Mode Auth Bypass is Correctly Guarded

**Severity:** LOW

**CWE:** CWE-287 (Improper Authentication)

**OWASP Top 10:** A07:2021 - Identification and Authentication Failures

**Description:**

The `get_current_user()` function in `/Volumes/Work/Dev/project-score-card/backend/app/core/auth.py` (lines 111-118) allows authentication bypass when `settings.debug=True` AND no token is present. This is correctly implemented because:

1. It only triggers when `settings.debug` is `True` AND `token is None` -- if a token IS provided (even in debug mode), it is validated normally
2. Production sets `DEBUG=false` (`/Volumes/Work/Dev/project-score-card/infrastructure/templates/user_data.sh`, line 124)
3. A security warning is logged when the bypass activates
4. The lifespan handler displays a prominent warning at startup

However, the bypass grants `["user", "admin"]` roles to the mock dev user, which means any unauthenticated request in debug mode gets admin privileges. This is generous for development but could mask authorization bugs during development.

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/core/auth.py, lines 111-118
if settings.debug and token is None:
    logger.warning(
        "SECURITY: Development mode authentication bypass used. "
        "No authentication token provided - using mock development user."
    )
    return TokenData(
        user_id="dev-user-id",
        roles=["user", "admin"],  # Full privileges in dev mode
    )
```

**Remediation:**

Consider granting only `["user"]` role by default in dev bypass to better test authorization boundaries during development. Admin testing can be done via `generate_jwt_token.py --roles admin`.

**Attacker Profile:** N/A (development-only, not reachable in production)

---

### Finding SEC-011

**Title:** User Profile Cached in localStorage Without Integrity Verification

**Severity:** LOW

**CWE:** CWE-345 (Insufficient Verification of Data Authenticity)

**OWASP Top 10:** A08:2021 - Software and Data Integrity Failures

**Description:**

The `AuthContext.tsx` stores user profile data (including the `role` field) in localStorage under the `auth_user` key. This data is used for UI rendering (showing/hiding admin tabs, displaying user name). A user with browser DevTools access could modify this cached data to make the UI display admin-only elements.

However, the security impact is minimal because:
1. All authorization decisions are made server-side via JWT claims
2. The cached data is only used for UI display
3. On page reload, `validateSession()` fetches fresh user data from `/auth/me` and overwrites the cache
4. Any API request to admin endpoints would fail with 403 because the JWT role claim cannot be modified client-side

**Evidence:**

```typescript
// /Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx, line 48
localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user));
```

**Remediation:**

This is acceptable given the server-side enforcement. For defense-in-depth, the comment in the code correctly documents this is a UI cache only. No code changes needed.

**Attacker Profile:** Script kiddie (but impact is UI-only, no privilege escalation)

---

### Finding SEC-012

**Title:** Stale Legacy Login Page Ships with Auth Bypass Link

**Severity:** LOW

**CWE:** CWE-200 (Exposure of Sensitive Information)

**OWASP Top 10:** A05:2021 - Security Misconfiguration

**Description:**

The file `/Volumes/Work/Dev/project-score-card/frontend/src/pages/Login.tsx` (distinct from `LoginPage.tsx`) contains a hardcoded "bypass auth" link (line 87) and an `alert()` call for Google OAuth (line 22). This appears to be a legacy file that has been superseded by `LoginPage.tsx`.

The `App.tsx` uses `LoginPage` (from `LoginPage.tsx`) for the login route in production mode, and `Login.tsx` is not imported. However, the file remains in the codebase and would be included in the production bundle if tree-shaking does not eliminate it (it likely is eliminated since nothing imports it).

**Evidence:**

```typescript
// /Volumes/Work/Dev/project-score-card/frontend/src/pages/Login.tsx, lines 82-88
<div className="text-xs text-gray-500 text-center">
  <p>For development mode, navigate to:</p>
  <a href="/" className="text-blue-600 hover:text-blue-800 font-medium">
    Dashboard (bypasses auth)
  </a>
</div>
```

**Remediation:**

Delete `/Volumes/Work/Dev/project-score-card/frontend/src/pages/Login.tsx` since `LoginPage.tsx` is the actual login page. This removes dead code and eliminates confusion.

**Attacker Profile:** N/A (not reachable in production routing)

---

### Finding SEC-013

**Title:** JWT Algorithm Correctly Pinned to HS256

**Severity:** INFO (Positive Finding)

**CWE:** CWE-327 (Use of a Broken or Risky Cryptographic Algorithm)

**OWASP Top 10:** A02:2021 - Cryptographic Failures

**Description:**

The JWT implementation correctly pins the algorithm to `HS256` both at signing and verification:

- Signing: `jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)` (line 89)
- Verification: `jwt.decode(token, secret_key, algorithms=[ALGORITHM])` (line 139)

The `algorithms` parameter in `jwt.decode()` is a list containing only `["HS256"]`, which prevents algorithm confusion attacks (e.g., an attacker crafting a token with `alg: none` or `alg: RS256` using the HMAC secret as a public key).

**Evidence:**

```python
# /Volumes/Work/Dev/project-score-card/backend/app/core/auth.py
ALGORITHM = "HS256"  # line 18
# ...
jwt.decode(token, secret_key, algorithms=[ALGORITHM])  # line 139
```

**Remediation:** None needed. This is a textbook-correct implementation.

---

### Finding SEC-014

**Title:** Missing `__Host-` or `__Secure-` Cookie Prefix

**Severity:** LOW

**CWE:** CWE-1004 (Sensitive Cookie Without 'HttpOnly' Flag) -- broad cookie security category

**OWASP Top 10:** A05:2021 - Security Misconfiguration

**Description:**

The cookie name is `access_token` (`COOKIE_NAME = "access_token"` at `/Volumes/Work/Dev/project-score-card/backend/app/core/auth.py`, line 19). Modern browsers support cookie prefixes that provide additional protections:

- `__Host-` prefix: Browser enforces `Secure`, `Path=/`, and no `Domain` attribute. Prevents cookie injection via subdomains.
- `__Secure-` prefix: Browser enforces `Secure` flag.

Since the cookie uses `path="/api"` (not `/`), the `__Host-` prefix cannot be used (it requires `Path=/`). The `__Secure-` prefix could be used in production.

**Impact:**

Minimal. Without the prefix, a subdomain takeover attack could potentially inject a cookie with the same name. However, the single-domain deployment architecture and SameSite=Lax mitigate this risk.

**Remediation:**

Consider renaming the cookie to `__Secure-access_token` in production. This requires the `Secure` flag, which is already set in production. However, this would need conditional naming (different in dev vs prod) which adds complexity for marginal benefit in the current architecture.

**Attacker Profile:** Advanced APT (requires subdomain takeover)

---

### Finding SEC-015

**Title:** Axios 401 Interceptor Properly Handles Session Expiry

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The axios response interceptor in `/Volumes/Work/Dev/project-score-card/frontend/src/services/api/client.ts` (lines 11-19) correctly handles 401 responses by:
1. Clearing the localStorage user cache
2. Redirecting to `/login`

This ensures that when a JWT expires (after 24 hours), the user is cleanly redirected to re-authenticate rather than seeing broken API responses.

**Evidence:**

```typescript
// /Volumes/Work/Dev/project-score-card/frontend/src/services/api/client.ts, lines 11-19
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_user');
      globalThis.location.href = '/login';
    }
    return Promise.reject(error);
  },
);
```

**Remediation:** None needed.

---

### Finding SEC-016

**Title:** Security Headers Middleware Properly Configured

**Severity:** INFO (Positive Finding)

**CWE:** N/A

**OWASP Top 10:** N/A

**Description:**

The `SecurityHeadersMiddleware` in `/Volumes/Work/Dev/project-score-card/backend/app/core/security_middleware.py` sets comprehensive security headers:

- `Strict-Transport-Security` (HSTS) in production
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy` with restrictive directives
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` restricting sensitive APIs

The CSP includes `frame-ancestors 'none'` which provides clickjacking protection alongside `X-Frame-Options: DENY`.

**Remediation:** None needed. Headers are well configured.

---

### Finding SEC-017

**Title:** `useUsers.ts` Uses Separate `fetch()` Instead of Shared Axios Client

**Severity:** LOW

**CWE:** CWE-1188 (Insecure Default Initialization of Resource)

**OWASP Top 10:** A05:2021 - Security Misconfiguration

**Description:**

The `useUsers.ts` hook (`/Volumes/Work/Dev/project-score-card/frontend/src/hooks/useUsers.ts`) implements its own `fetchWithAuth()` wrapper using raw `fetch()` instead of using the shared axios client from `services/api/client.ts`. While it correctly includes `credentials: 'include'`, it constructs URLs using `${API_URL}/api/admin/users` rather than the relative `/api` path used by the axios client.

This means:
1. The 401 interceptor (auto-redirect to login) does NOT apply to admin user API calls
2. If `VITE_API_URL` is misconfigured or different from the cookie origin, these requests could fail silently

**Evidence:**

```typescript
// /Volumes/Work/Dev/project-score-card/frontend/src/hooks/useUsers.ts, lines 9-17
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  const response = await fetch(url, { ...options, headers, credentials: 'include' });
  // ...
}
```

**Remediation:**

Refactor `useUsers.ts` to use the shared axios client instead of raw `fetch()`. This ensures consistent 401 handling, URL resolution, and credential management across all API calls.

**Attacker Profile:** N/A (not directly exploitable, but increases maintenance risk)

---

### Finding SEC-018

**Title:** `AuthContext.tsx` Uses Absolute URL for API Calls

**Severity:** LOW

**CWE:** CWE-1188 (Insecure Default Initialization of Resource)

**OWASP Top 10:** A05:2021 - Security Misconfiguration

**Description:**

The `AuthContext.tsx` (`/Volumes/Work/Dev/project-score-card/frontend/src/contexts/AuthContext.tsx`, line 12) constructs API URLs using:

```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

In production, if `VITE_API_URL` is set to the production domain (e.g., `https://hub.example.com`), the login request goes to `https://hub.example.com/api/auth/google`. The cookie is then set on the `hub.example.com` domain. Subsequent requests from the axios client use relative paths (`/api/...`) which resolve to the same origin. This works correctly.

However, having two different URL resolution strategies (absolute in AuthContext, relative in axios client) creates a subtle mismatch risk. If the frontend is served from a different origin than `VITE_API_URL`, the cookie set during login would not be sent by the axios client (different origin = different cookie jar).

In the current production setup (`/Volumes/Work/Dev/project-score-card/infrastructure/templates/user_data.sh`, line 311: `VITE_API_URL=https://${domain_name}`), everything is on the same domain, so this works. But it is fragile.

**Remediation:**

Consider using the shared axios client for auth requests too, or use relative URLs in `AuthContext.tsx` as well. This eliminates the dual-URL-strategy risk.

---

## Secure Architecture Recommendations

### 1. Defense-in-Depth Summary

The implementation provides multiple layers of protection:

| Layer | Protection | Status |
|-------|-----------|--------|
| Token Storage | httpOnly cookie (immune to XSS theft) | IMPLEMENTED |
| Cookie Scope | `path=/api` (minimized exposure) | IMPLEMENTED |
| Cookie Transport | `Secure` flag in production | IMPLEMENTED |
| CSRF | SameSite=Lax + JSON + CORS | IMPLEMENTED |
| JWT Validation | HS256 pinned, expiry enforced | IMPLEMENTED |
| CORS | Explicit origins, no wildcard | IMPLEMENTED |
| Security Headers | CSP, HSTS, X-Frame-Options, etc. | IMPLEMENTED |
| Token Expiry | 24-hour JWT lifetime | IMPLEMENTED |
| Logout | Server-side cookie deletion | IMPLEMENTED |

### 2. Recommended Hardening (Non-Blocking)

- **Token rotation**: Consider implementing refresh tokens with shorter-lived access tokens (e.g., 15 min access + 7 day refresh) to limit the window of a stolen JWT
- **Logout invalidation**: The current JWT-based auth has no server-side token revocation. If a user's account is compromised, the JWT remains valid until expiry. Consider a token blacklist (Redis-backed) for immediate revocation
- **Cookie `__Secure-` prefix**: Add in production for additional browser-enforced security
- **Consolidate HTTP clients**: Move all frontend API calls to use the shared axios client for consistent credential and error handling

### 3. Secrets Management

The implementation correctly:
- Loads JWT_SECRET_KEY from environment (not hardcoded)
- Uses AWS Secrets Manager in production
- Validates that the secret is not empty before signing

### 4. Logging and Monitoring

The implementation includes:
- Security warning logs for dev bypass usage
- Login/logout event logging with user IDs
- Failed authentication attempt logging (Google token validation failures)
- Domain restriction violation logging

---

## DevSecOps Pipeline Hardening

### Current CI/CD Security

The project has:
- Backend pytest suite with 750+ tests including dedicated security tests
- Frontend vitest suite with 214+ tests
- OIDC-based AWS authentication (no long-lived credentials)
- ECR for container image storage

### Recommended Additions

1. **Cookie security tests**: Add integration tests that verify the `Set-Cookie` header attributes in actual HTTP responses (not just unit tests of `get_cookie_settings()`)
2. **CORS preflight tests**: Add tests that verify cross-origin requests are properly blocked
3. **Dependency scanning**: Ensure `npm audit` and `pip audit` run in CI
4. **Secret scanning**: Add git-secrets or similar pre-commit hook to prevent accidental secret commits

---

## Compliance Mapping

### OWASP Top 10 (2021) Coverage

| Category | Finding | Status |
|----------|---------|--------|
| A01: Broken Access Control | CSRF protection via defense-in-depth | PASS |
| A02: Cryptographic Failures | HS256 pinned, secrets from env | PASS |
| A03: Injection | N/A for this refactor | N/A |
| A04: Insecure Design | Cookie-first token resolution | PASS |
| A05: Security Misconfiguration | CORS properly configured | PASS |
| A06: Vulnerable Components | N/A for this refactor | N/A |
| A07: Auth Failures | httpOnly cookie, no token in body | PASS |
| A08: Data Integrity | localStorage cache is UI-only | ACCEPTABLE |
| A09: Logging Failures | Auth events logged | PASS |
| A10: SSRF | N/A for this refactor | N/A |

---

## Summary

The JWT httpOnly cookie refactor is well-implemented and follows security best practices. The migration successfully eliminates the XSS token theft vector that existed with localStorage-based JWT storage. No CRITICAL or HIGH severity findings were identified. The LOW and MEDIUM findings are non-blocking quality improvements rather than exploitable vulnerabilities.

**Recommendation: APPROVE for production deployment.**

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 5 |
| INFO | 12 (includes 8 positive findings) |
