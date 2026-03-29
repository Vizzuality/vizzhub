# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2026-03-29] - Observability

### Added

#### Backend
- Structured logging with structlog (JSON in prod, console in dev)
- Request ID middleware (X-Request-ID header, bound to all logs)
- Health endpoints: `/health/live` (liveness), `/health/ready` (readiness)
- Worker heartbeat via Redis key with 120s TTL
- Sentry integration with `before_send` filter (401/403/404 excluded)
- Prometheus HTTP metrics via `/metrics` endpoint
- Worker metrics: `arq_jobs_total`, `arq_job_duration_seconds`

#### Frontend
- Sentry integration with React Router v6 browser tracing
- `Sentry.ErrorBoundary` replaces manual ErrorBoundary
- Source maps upload via `@sentry/vite-plugin` (conditional on SENTRY_AUTH_TOKEN)

### Changed
- All 44 backend modules migrated from stdlib logging to structlog
- Log events follow `{entity}_{action}` naming convention
- Security logger rewritten to use structlog

## [2026-01-19] - Code Simplification & Test Fixes

### Changed

#### Backend Simplifications
- **indicators.py**: Replaced nested if/else with dictionary lookups for cleaner code
  - `_normalize_pm_satisfaction`: Now uses dict lookup instead of nested conditionals
  - `_normalize_client_survey`: Eliminated nonlocal variables with direct loop iteration
  - `_normalize_test_maturity`: Replaced nested helper function with explicit loop

- **dimensions.py**: Simplified conditional logic
  - `CostCalculator.calculate`: Converted if/else to ternary expression
  - `SatisfactionCalculator.calculate`: Added early return pattern for clarity

- **final_score.py**: Consolidated repetitive code
  - Replaced 8 manual weight assignments with dict comprehension
  - Cleaner calculation of weighted sum using generator expression

#### Frontend Simplifications
- **utils/formatters.ts** (NEW): Created shared date formatting utility
  - Centralized `formatDate` function eliminates code duplication across components

- **ScoreCard.tsx**: Improved color logic organization
  - Added `getScoreLevel` helper to consolidate duplicate color determination
  - Created `getScoreColor` and `getScoreBgColor` functions using the helper

- **Login.tsx**: Better component organization
  - Extracted `GoogleIcon` as separate component
  - Extracted `handleGoogleLogin` function for better readability

- **AuthContext.tsx**: Naming convention improvements
  - Renamed constant to `DEFAULT_AUTH_STATE` (SCREAMING_SNAKE_CASE)

- **api.ts**: Simplified HTTP interceptors
  - Cleaner request/response interceptor logic

### Fixed

#### Test Infrastructure
- **conftest.py**: Fixed environment variable loading order
  - JWT_SECRET_KEY and other env vars now set BEFORE app imports
  - Prevents settings object initialization errors in tests
  - Added DATABASE_URL default for test environment

- **conftest.py**: Fixed test isolation issues
  - Database tables now dropped before creation in each test (clean slate)
  - Rate limiter state reset between tests prevents "429 Too Many Requests" errors
  - All limiter instances (main, projects, metrics, collectors, scores, config, oauth) now reset

- **main.py**: Fixed validation error JSON serialization
  - ValueError objects in validation errors now properly serialized to strings
  - Prevents `TypeError: Object of type ValueError is not JSON serializable`

- **scores.py**: Fixed rate limiter parameter naming
  - Changed `http_request: Request` to `request: Request` (required by slowapi)
  - Changed `request: ScoreRequest` to `score_request: ScoreRequest`

- **test_api.py**: Fixed score field assertion
  - Updated from `final_score` to `score` to match FinalScore model

### Test Results

**All 312 tests passing (100%)**
- Backend: 216/216 tests ✓
- Frontend: 96/96 tests ✓
- Test coverage: ~85%

### Impact

- ✅ Code is more maintainable and easier to understand
- ✅ No functionality changes - all behavior preserved
- ✅ All tests passing with improved test isolation
- ✅ Better test infrastructure prevents future rate limiting issues

---

## Previous Changes

See git history for earlier changes. This changelog started on 2026-01-19.
