# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Project Scorecard evaluates software development projects across 8 dimensions (P_time, P_cost, P_quality, P_value, P_satisfaction, P_flow, P_engineering, P_risk). Migrated from Google Sheets to FastAPI + React.

## Commands

### Development (Recommended - Local without Docker)

```bash
# Backend
cd backend
python run_server.py                          # Start backend server
python test_jira_oauth.py PROJECT_KEY        # Test Jira OAuth collection

# ARQ Worker (for background jobs - requires Redis)
cd backend
arq app.worker.settings.WorkerSettings        # Start background job worker

# Frontend
cd frontend
npm run dev                                   # Start development server

# Generate JWT tokens (for testing authenticated endpoints)
cd backend
python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
```

### Docker (Alternative)

```bash
# Start all services (PostgreSQL, backend, frontend, worker, redis)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker                     # Background job worker

# Restart after changes
docker-compose down && docker-compose up -d --build
```

### Backend (FastAPI)

```bash
cd backend

# Run tests
pytest                                        # All backend tests (~760 total)
pytest tests/test_calculators.py              # Single file
pytest tests/test_normalizers.py::TestLowerIsBetter  # Single class
pytest -k "test_perfect_score"                # By name pattern

# Integration tests (60 tests - critical for regression prevention)
pytest tests/test_integration.py              # All integration tests
pytest tests/test_integration.py::TestScoresAPIIntegration  # Scores API
pytest tests/test_integration.py::TestAuthMiddlewareIntegration  # Auth

# Security tests
pytest tests/test_auth.py                     # Authentication tests (17 tests)
pytest tests/test_oauth_service.py            # OAuth service (17 tests)
pytest tests/test_jira_collector.py           # Jira collector (25 tests)
pytest tests/test_api_security.py             # API security (23 tests)
pytest tests/test_security_middleware.py      # Security headers (13 tests)
pytest tests/test_security_logger.py          # Security logging (9 tests)
pytest tests/test_oauth_state.py              # CSRF protection (10 tests)
pytest tests/test_jira_collector_jql_injection.py  # JQL injection (11 tests)

# Run with coverage
pytest --cov=app --cov-report=html

# Linting
ruff check app/
black app/

# Run server manually
python run_server.py                          # Recommended
# OR
uvicorn app.main:app --reload
```

### Frontend (React)

```bash
cd frontend
npm run dev      # Development server (http://localhost:5173)
npm run build    # Production build
npm run lint     # ESLint
npm test         # Run tests (~325 total)

# Theme (shadcn/tweakcn)
# Current theme: https://tweakcn.com/r/themes/cmkliqxix000d04la3624132s
# To regenerate theme CSS:
pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/cmkliqxix000d04la3624132s
# Theme uses OKLCH color space, Outfit font (sans), Fira Code font (mono)
```

## Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code, auto-deploys to AWS |
| `dev` | Active development (default branch) |
| `feature/*` | Feature branches → PR to `dev` |

- All PRs target `dev` by default
- Merge `dev` → `main` triggers production deployment
- Delete feature branches after merge

**CI/CD:**
- Push to `main` or `dev` → runs CI tests (`.github/workflows/ci.yml`)
- Push to `main` only → builds, pushes to ECR, deploys to production (`.github/workflows/deploy.yml`)

## Architecture

### Modular Architecture Rules (MUST FOLLOW)

The Hub is evolving into a multi-module platform (scorecard, tracker, future tools). These rules apply to ALL new code and to any existing code being modified. See `docs/vizztracker_integration.md` for full context.

**1. New code goes in modules, not in flat `app/` directories.**

- New tracker code → `app/modules/tracker/`
- New frontend features for tracker → `src/modules/tracker/`
- Existing scorecard code stays in place until organically migrated

**2. Core entities (`Project`, `User`) live in `app/core/models/`.**

When `core/models/` exists, import from there. Until extracted, existing `app/models/` paths are acceptable for scorecard code.

**3. Cross-module imports go through `public.py` ONLY.**

```python
# ALLOWED
from app.modules.tracker.services.public import get_budget_summary
from app.core.models.project import ProjectDB

# FORBIDDEN — never import another module's internals
from app.modules.scorecard.services.calculators.time import TimeCalculator
```

**4. Write isolation, read flexibility.**

Each module only writes to its own tables (scorecard cannot INSERT into tracker's `contracts`). For business logic reads, use `public.py` interfaces. For analytical/reporting reads (dashboards, exports), direct JOINs across module tables are allowed in dedicated query services under `app/core/services/`.

**5. Entity placement decision rule:**

- Needed by ALL modules → `core/` (shared schema)
- One module creates it, others read → owner module + `public.py`
- Only one module uses it → module-private

**6. Frontend modules are self-contained.**

Each module under `src/modules/` has its own `components/`, `hooks/`, `pages/`. Shared UI primitives, auth, and utilities live in `src/shared/`.

**7. Module routers aggregate sub-routers. `main.py` only mounts module-level routers.**

Each module has a `router.py` that aggregates its sub-routers with `include_router`. Prefixes are always defined in `include_router`, never inside router files. No two routers share the same prefix.

**8. New endpoints use project-scoped permissions.**

New tracker endpoints must use `ProjectViewer`, `ProjectContributor`, or `ProjectManager` dependencies from `app/core/permissions.py` (not bare `CurrentUser`). Existing scorecard endpoints can keep `CurrentUser` until migrated. Admin role always bypasses project-level checks.

**9. URL is the single source of truth for frontend view state.**

All user-visible state (selected period, active tab, filters, snapshot type) must be reflected in the URL via search params or path segments. Use `useUrlState` hook from `src/shared/hooks/useUrlState.ts` instead of bare `useState` for any view state. Tabs use nested routes, not `<Tabs defaultValue>`. Page reload must preserve the exact view. New modules (tracker) must be URL-driven from day 1.

### Backend Data Flow

```
Raw Metrics → Normalizers → Indicators (0-1) → Calculators → Scores (0-100)
```

1. **Collectors** (`services/collectors/`): Fetch data from Jira/GitHub APIs. Collectors only collect—they do not interpret. Return typed Pydantic models (`JiraCollectedMetrics`, `GitHubCollectedMetrics`) for type safety.

2. **Normalizers** (`services/normalizers/`): Transform raw metrics to 0-1 scale using these patterns:
   - Higher is better: `min(1, value)`
   - Lower is better: `min(1, target / max(value, 0.001))`
   - Missing data: return 0.5 (neutral)
   - Strict zero target: if target=0 and value>0, return 0

3. **Calculators** (`services/calculators/`): Apply weights from database configuration to produce 0-100 scores. Each dimension has its own calculator class.

4. **FinalScoreCalculator**: Aggregates all 8 dimension scores using global weights.

### Configuration

All weights, targets, and ideals are stored in the `config_parameters` database table. The seed file is `backend/seeds/config_parameters.csv`. Weight groups must sum to 1.0. The `ScoringConfig` class loads from DB at startup and provides `validate_weights()`.

**Access methods**:
- `get_target(name)` - Threshold values for color coding (minimum acceptable)
- `get_ideal(name)` - Benchmark values for scoring (100 points)
- `get_weight(group, name)` - Weight values for calculations
- `get_constant(name)` - System constants (sev1_cap, grace_days)

### Targets vs Ideals

**Critical distinction** for accurate scoring:

| Concept | Purpose | Example |
|---------|---------|---------|
| **Target** | Minimum acceptable (color coding) | SPI target = 0.8 (80% = green threshold) |
| **Ideal** | Perfect score benchmark | SPI ideal = 1.0 (100% = 100 points) |

**Why this matters**: A project with SPI = 0.85 should show green (above 0.8 target) but score 85 points (not 100). Without ideals, metrics at 85% were incorrectly scoring 100%.

**Currently only SPI and CPI have explicit ideals** (both = 1.0). Other metrics infer ideal from their type (e.g., defect_density ideal is 0).

### Project Status & Lifecycle

Projects have a `status` field: `in_progress` (default) or `finished`.

**Important date fields:**

| Field | Purpose | Example |
|-------|---------|---------|
| `end_date` | Contract/planned end date | Project planned to end Dec 2025 |
| `finished_at` | Actual completion date | Project actually finished Oct 2025 |

- `end_date` is set manually and represents the contractual deadline
- `finished_at` is set when marking project as finished (via month/year selector)
- **Timeline uses `finished_at`** to stop showing future months for finished projects
- On "Reopen Project", `finished_at` is cleared (`clear_finished_at: true`)

**When finished**:
- Timeline stops at `finished_at` month (no indefinite growth)
- Jira/GitHub collectors are blocked (returns 400 error)
- Regular metric updates blocked (only end-of-project metrics allowed)
- End-of-project metrics become available: Strategic Impact, Client Survey

**End-of-project metrics**:
- `strategic_impact`: LOW (25), MEDIUM (55), HIGH (80), TRANSFORMATIONAL (100)
- `client_survey`: 8 questions (1-5 scale) with weighted average

### Metrics & Snapshot Types

The `metrics` table stores all collected metrics with two snapshot types:

| Type | Description | Date Range |
|------|-------------|------------|
| **cumulative** | Project-to-date metrics | `project.start_date` → `period_end` |
| **punctual** | Single month metrics | First day of month → Last day of month |

**Key rules:**
- **Default is CUMULATIVE** - All API endpoints default to querying/creating cumulative metrics
- **Unique constraint**: `(project_id, period_year, period_month, snapshot_type)` - one record per type per month
- **Capture endpoint** (`POST /projects/{id}/capture-period`) creates BOTH types automatically
- **"Collect Metrics" button** in UI captures metrics for the **selected period** on the timeline
- **Overwrite warning** - If period already has data, user must confirm before overwriting
- **Historical period warning** - Manual metric updates to past periods show confirmation dialog

**Snapshot type enum:**
```python
class SnapshotType(str, Enum):
    PUNCTUAL = "punctual"      # Data for single month only
    CUMULATIVE = "cumulative"  # Data from project start to month end
```

**API filtering:**
```
GET /api/scores/project/{id}?snapshot_type=cumulative  # default
GET /api/metrics/project/{id}/history?snapshot_type=punctual  # explicit
```

**Manual field synchronization:**
When a user updates manual fields (EVM, milestones, governance, etc.), they are automatically synced to the other snapshot type for the same period. This ensures consistency for project-level data that doesn't depend on date ranges.

| Field Type | Examples | Synced? | Reason |
|------------|----------|---------|--------|
| Manual | `milestones`, `governance_exceptions`, `budget_total`, `test_maturity` | ✅ Yes | Project-level data, same for any date range |
| Collector | `bugs_total`, `lead_time_days`, `total_merged_prs` | ❌ No | Different values for different date ranges |

Manual fields are defined in `MetricsDB.MANUAL_FIELDS`.

### Key Design Rules

- Scores are computed on-the-fly, not stored (ensures config changes apply immediately). Results are cached in Redis with write-through warming and invalidation on every write path. See **Redis Score Cache** section.
- Sev1 incidents cap P_quality at 60 points
- Milestones have a grace period (default 3 days)
- Disabled governance tools get penalized (score = 0), not neutral
- **Metrics consolidation**: Multiple metrics records with same `period_end` are consolidated (`_consolidate_metrics` in `app/api/scores.py`). This handles multiple collector runs creating separate records.
- **Ideals for ratio metrics**: SPI/CPI use ideal=1.0 for scoring; value/ideal gives accurate percentage
- **No trailing slashes**: `redirect_slashes=False` in FastAPI. Define routes as `""` not `"/"`. Trailing slash redirects (307) break auth cookies behind ALB.
- **PUT vs PATCH**: Use the correct HTTP method. `PUT` = full resource replacement. `PATCH` = partial update. They are not interchangeable. Match frontend calls, backend decorators, and tests to the same method.

### Database

PostgreSQL with async SQLAlchemy. Tables: `projects`, `metrics`, `oauth_tokens`, `config_parameters`. Indicators and scores are computed, not persisted. Configuration is loaded from `config_parameters` at startup.

**Metrics table key columns:**
```sql
-- Period identification
period_year INT NOT NULL,
period_month INT NOT NULL,
snapshot_type VARCHAR(20) NOT NULL DEFAULT 'cumulative',

-- Unique constraint
UNIQUE (project_id, period_year, period_month, snapshot_type)
```

### Database Transactions with FastAPI

**CRITICAL**: FastAPI's `DBSession` dependency manages transactions automatically.

❌ **WRONG** - Manual transaction conflicts with dependency:
```python
async with db.begin():
    result = await some_db_operation(db)
```

✅ **CORRECT** - Let dependency handle transactions:
```python
result = await some_db_operation(db)
await db.commit()  # Only if needed explicitly
```

**Why**: The `DBSession` dependency already wraps the request in a transaction context. Adding `async with db.begin()` creates a nested transaction conflict that triggers:
```
sqlalchemy.exc.InvalidRequestError: Can't operate on closed transaction inside context manager.
```

**Exception**: Only use manual `db.begin()` if you're NOT using the DBSession dependency (e.g., in background tasks or scripts outside FastAPI request context).

### Slack Notifications System

Automated alerts to Slack channels for business and security issues.

**Architecture:**
- **Business alerts** → Leadership channel (budget exceeded, timeline at risk, project overdue)
- **Project alerts** → Per-project channels (Dependabot vulnerabilities)

**Database tables:**
- `slack_config` - Global config (bot token, leadership channel)
- `alert_definitions` - Predefined alert types with enable/disable
- `message_templates` - Customizable Slack message templates
- `alert_silences` - Per-project alert muting
- `alert_notifications` - Log of sent alerts
- `dependabot_alerts_tracked` - Track notified vulnerabilities
- `scheduled_job_runs` - Cron job execution history

**Scheduled jobs (ARQ cron):**
- `check_dependabot_alerts` - Daily at 8:00 UTC, checks GitHub Dependabot
- `check_business_alerts` - Daily at 9:00 UTC, checks budget/timeline/overdue

**Dependabot alert strategy:**

| Situation | Action |
|-----------|--------|
| Alert not tracked | **Notify** + track |
| Alert already tracked | No notification |
| Critical unresolved > 2 days | Send reminder |
| High unresolved > 7 days | Send reminder |
| Alert disappears from GitHub | Mark as resolved |

- Notifications include link to GitHub: `https://github.com/{repo}/security/dependabot/{id}`
- `last_notified_at` tracks when each alert was last notified (initial or reminder)
- Templates support variables: `{project_name}`, `{vuln_severity}`, `{vuln_package}`, `{vuln_cve}`, `{vuln_url}`, `{vuln_age_days}`

**Business alert strategy:**
- Monthly throttling per project per alert type
- Alerts: `budget_exceeded` (≥100%), `timeline_at_risk` (velocity-based), `project_overdue` (>30 days past end_date)

**Key services:**
- `app/services/slack_service.py` - Slack API wrapper (send_message, list_channels, test_connection)
- `app/services/alert_service.py` - Template rendering, silence checking, notification logging
- `app/services/collectors/dependabot.py` - Fetch high/critical Dependabot alerts

**Frontend:**
- Admin page with tabs: Configuration, Slack, Notifications, Jobs
- Project form includes Slack channel selector

### Background Jobs (ARQ + Redis)

Long-running tasks (batch historical capture, scheduled alerts) run asynchronously via ARQ with Redis as the message broker.

**Architecture:**
```
Frontend → POST /jobs/capture-history → Creates Job record → Enqueues to Redis → ARQ Worker picks up
                                              ↓
                                     Frontend polls GET /jobs/{id} for status/progress
```

**Components:**
- `app/worker/settings.py` - ARQ worker configuration (timeouts, retries, Redis connection)
- `app/worker/tasks.py` - Task definitions (e.g., `capture_history_task`)
- `app/models/job.py` - Job model for tracking status in PostgreSQL
- `app/services/job_service.py` - CRUD operations for jobs
- `app/api/jobs.py` - REST endpoints for job management

**Job Status Flow:**
```
PENDING → RUNNING → COMPLETED
                  → FAILED
        → CANCELLED
```

**Running the worker:**
```bash
# Local development
cd backend
arq app.worker.settings.WorkerSettings

# Docker (worker starts automatically with docker-compose up)
docker-compose logs -f worker
```

**Production deployment:**
- Worker service in `docker-compose.yml` has `restart: unless-stopped`
- For Kubernetes: use a Deployment with replicas and health checks
- For systemd: create a service unit with `Restart=always`

**Configuration** (`.env`):
```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
```

**Key design decisions:**
- Jobs are tracked in PostgreSQL (not just Redis) for persistence and querying
- Progress updates are stored in DB for frontend polling
- 5-second delay between months to avoid rate limiting
- Frontend uses localStorage to persist active job IDs across page reloads

**Example from codebase** (`oauth.py`):
```python
# OAuth callback handler
async def jira_callback(
    db: DBSession,  # ← This already manages transactions
    code: str,
) -> dict:
    # ❌ WRONG: async with db.begin():
    token = await OAuthService.exchange_jira_code_for_token(code, db)
    await db.commit()  # ✅ Explicit commit when needed
    return {"status": "success"}
```

### Redis Score Cache

Computed scores are cached in Redis to eliminate N+1 network calls on the projects index page. The cache is **optional** — if Redis is unavailable, endpoints fall back to on-demand computation.

**Cache key**: `scores:latest:{project_id}:{snapshot_type}` — stores serialized `ScoreResponse` JSON.

**Strategy:**

| Event | Action |
|-------|--------|
| `GET /scores/project/{id}` (latest, no year/month) | Read-through: check cache → compute on miss → cache result |
| `POST /scores/batch` | MGET from cache → compute misses → SET misses → return all |
| `POST /projects/{id}/capture-period` | Write-through: cache freshly computed scores for both snapshot types |
| Metrics create/delete (`POST/DELETE /metrics/...`) | Invalidate: delete both snapshot type keys for project |
| Legacy collectors (`POST /collect/...`) | Invalidate: delete both snapshot type keys for project |
| Config update (`PUT /config/parameters`) | Invalidate all: SCAN + delete all `scores:latest:*` keys, reload `ScoringConfig` |
| Worker batch capture (`capture_history_task`) | Invalidate: delete keys after each month's upsert |

**TTL**: 1 hour safety net. Invalidation is the primary freshness mechanism.

**Graceful degradation**: Every `ScoreCacheService` method wraps Redis calls in `try/except` — Redis errors are logged as warnings, never propagated to callers.

**Key files:**
- `app/services/score_cache.py` — `ScoreCacheService` class
- `app/api/deps.py` — `OptionalScoreCache` dependency (`None` when Redis unavailable)
- `app/main.py` — Redis client init/cleanup in lifespan
- `app/worker/settings.py` — Redis client init for worker context

**Dependency**: `OptionalScoreCache` (from `deps.py`) is `ScoreCacheService | None`. Always check for `None` before calling cache methods:
```python
cache: OptionalScoreCache  # injected by FastAPI

if cache:
    await cache.invalidate(str(project_id))
```

**Frontend**: The projects index page uses `POST /scores/batch` via `useProjectScoresMap` hook (single request instead of N parallel `GET` calls). Batch query key `['scores', 'batch', ...sortedIds]` is invalidated by `invalidateProjectData()` in `cacheUtils.ts`.

### Production Deployment (AWS)

Hub is deployed to AWS using OpenTofu/Terraform infrastructure-as-code.

**Architecture:**
```
Internet → ALB (HTTPS/ACM) → EC2 (Docker Compose)
              ↓ path routing       ├── backend:8000
              ├── /api/*  ────────→│
              └── /*      ────────→├── frontend:5173
                                   ├── worker (arq)
                                   └── redis

                                   ↓
                            RDS PostgreSQL
```

**Components:**
| Service | Type | Purpose |
|---------|------|---------|
| ALB | - | HTTPS termination via ACM certificate, path-based routing |
| EC2 | t3.micro | Docker host (frontend, backend, worker, redis) |
| RDS | db.t4g.small | PostgreSQL 16 with automated backups |
| ECR | - | Container registry |
| Secrets Manager | - | Credentials storage |
| SSM | - | Secure shell access (no SSH) |

**CI/CD Pipeline:**
```
Push to main → CI Tests → Build Images → Push to ECR → SSM Deploy → Health Check
```

1. **CI Tests**: Backend pytest + frontend vitest
2. **Build**: Multi-stage Docker builds with SHA tags
3. **Push**: To ECR via OIDC (no long-lived credentials)
4. **Deploy**: SSM send-command writes docker-compose.prod.yml + `docker compose up -d`
5. **Verify**: Polling for command completion + health checks

**Key Files:**
```
infrastructure/
├── state.tf             # S3 + DynamoDB for state
├── main.tf              # Provider, backend config
├── alb.tf               # ALB, ACM certificate, target groups
├── network.tf           # VPC, subnets, routing
├── security_groups.tf   # ALB and EC2 security groups
├── ec2.tf               # Instance, IAM roles
├── rds.tf               # PostgreSQL database
├── ecr.tf               # Container registries
├── secrets.tf           # Secrets Manager
├── iam.tf               # GitHub OIDC provider
├── github.tf            # GitHub Actions role
├── cloudwatch.tf        # Log groups
├── variables.tf         # Input variables
├── outputs.tf           # Output values
└── docker-compose.prod.yml  # Production compose file

.github/workflows/
├── ci.yml               # Tests on push/PR
└── deploy.yml           # Build + deploy (SSM commands)
```

**AWS Access:**
- **Profile**: `vizzhub` (SSO via assume role)
- **Region**: `eu-west-3` (Paris)
- **EC2 Instance**: `i-097d6d92ab30d9622`

**Operations:**
```bash
# Connect to EC2 via SSM
aws ssm start-session --profile vizzhub --region eu-west-3 --target i-097d6d92ab30d9622

# Run commands on EC2 non-interactively (useful from Claude Code)
aws ssm send-command --profile vizzhub --region eu-west-3 \
  --instance-ids "i-097d6d92ab30d9622" \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["docker ps"]}'

# View container logs
docker compose -f /opt/hub/docker-compose.prod.yml logs -f backend

# Manual deploy
cd /opt/hub
export TAG="<git-sha>" ECR_URI="<account>.dkr.ecr.eu-west-3.amazonaws.com"
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin $ECR_URI
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d

# Refresh secrets (after updating in Secrets Manager)
/opt/hub/fetch-secrets.sh
docker compose -f /opt/hub/docker-compose.prod.yml restart backend worker
```

**Infrastructure Management:**
```bash
cd infrastructure

# Plan changes
tofu plan -var-file=environments/prod.tfvars

# Apply changes
tofu apply -var-file=environments/prod.tfvars

# View outputs
tofu output
```

See `infrastructure/README.md` for complete setup guide.

### Configuration Best Practices

**CRITICAL**: Never hardcode configuration values in `backend/app/config.py`.

- ❌ **WRONG**: `database_url: str = "postgresql://..."`
- ✅ **CORRECT**: `database_url: str = ""`

All default values belong in `.env` file, not in code:
- `config.py` - empty defaults (`""`, `[]`, `None`)
- `.env` - actual configuration values
- `.env.example` - example values with comments

This ensures:
1. Configuration is environment-specific
2. Secrets are not committed to git
3. Different developers can have different settings

### Authentication & Security

**Status**: Google SSO implemented with domain restriction + JWT in httpOnly cookies.

#### Google SSO (Implemented)

Users authenticate via Google Sign-In, restricted to `@vizzuality.com` domain.

**Configuration (`.env`):**
```
# Backend
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
ALLOWED_GOOGLE_DOMAIN=vizzuality.com
INITIAL_ADMIN_EMAIL=miguel.mendoza@vizzuality.com

# Frontend
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
VITE_BYPASS_AUTH=false
```

**User roles:**
- `user` - Default role for all new users
- `admin` - Can manage users via Admin > Users tab

**Flow:**
1. User clicks "Sign in with Google"
2. Google returns ID token to frontend
3. Frontend sends token to `POST /api/auth/google` with `credentials: 'include'`
4. Backend validates token, checks domain, creates/gets user
5. Backend sets JWT as httpOnly cookie (`access_token`, path `/api`, SameSite=Lax)
6. Response body returns only `{ user }` (no token in body)
7. All subsequent requests include cookie automatically (`withCredentials: true` / `credentials: 'include'`)

**JWT Storage (httpOnly cookies):**

| Aspect | Detail |
|--------|--------|
| Cookie name | `access_token` |
| Path | `/api` (only sent on API requests) |
| HttpOnly | Yes (inaccessible to JavaScript) |
| Secure | `true` in production, `false` when `DEBUG=true` |
| SameSite | `Lax` |
| Max age | `jwt_expire_hours * 3600` (default 24h) |
| CSRF | Not needed (SameSite=Lax + JSON Content-Type + CORS) |

**Token resolution order in `get_current_user()`:**
1. Read from cookie (`request.cookies.get("access_token")`)
2. Fall back to `Authorization: Bearer` header
3. If neither found and `DEBUG=true`, use dev bypass

**Frontend auth state:**
- Only `auth_user` is cached in `localStorage` (prevents UI flicker on reload)
- No token in `localStorage` — cookie is httpOnly
- `AuthContextType` has async `logout()`, no `getToken()`
- Axios client uses `withCredentials: true` (cookies sent automatically)
- `useUsers` hook uses `credentials: 'include'` on fetch calls

**Key endpoints:**
- `POST /api/auth/google` - Exchange Google token for JWT (set via cookie)
- `POST /api/auth/logout` - Clear httpOnly cookie
- `GET /api/auth/me` - Get current user info (validates session cookie)
- `GET /api/admin/users` - List users (admin only)
- `PATCH /api/admin/users/{id}` - Update user role (admin only)
- `DELETE /api/admin/users/{id}` - Delete user (admin only)

#### Development Mode
- Backend: `DEBUG=true` → CORS allows localhost, cookie `Secure=false` (required for local dev)
- Frontend: `VITE_BYPASS_AUTH=true` → Skip authentication entirely
- These are independent: use `DEBUG=true` + `VITE_BYPASS_AUTH=false` to test OAuth locally

#### Security Features Implemented
- ✅ Google SSO with domain restriction
- ✅ JWT in httpOnly cookies (XSS-proof token storage)
- ✅ Role-based access control (user/admin)
- ✅ User management UI in Admin panel
- ✅ OAuth CSRF protection (state parameter validation)
- ✅ Rate limiting (slowapi)
- ✅ Security headers middleware
- ✅ Input validation (JQL injection prevention, UUID validation)
- ✅ Security logging (structured JSON)

#### Admin Role Protection

**Backend** - Endpoints requiring admin role (use `AdminUser` dependency):
- `/admin/users/*` - User management
- `/admin/slack/*` - Slack configuration
- `/admin/alerts/*` - Alert definitions and templates
- `/admin/templates/*` - Message templates
- `/admin/jobs/*` - Scheduled jobs management
- `/notifications/*` - Notification log
- `/silences/*` - Alert silences
- `/global/calculate`, `/global/recalculate` - Global metrics calculation
- `/jobs/capture-history` (POST) - Create batch capture job
- `/jobs/{id}/cancel`, `/jobs/{id}/retry`, `/jobs/{id}` (DELETE) - Job management

**Frontend** - Admin-only UI elements:
- `/admin` route - Redirects non-admin to `/projects`
- Admin nav link - Hidden for non-admin users
- Batch Historical Capture section - Hidden in project details
- Calculate All / Recalculate buttons - Hidden in Global dashboard

### OAuth 2.0 (Jira)

Jira collector uses OAuth 2.0 with **classic scopes** (recommended by Atlassian).

**Scopes**: `read:jira-work read:jira-user`

**Setup**: See `docs/OAUTH_SETUP.md` for detailed instructions.

**Testing OAuth**:
```bash
cd backend
python test_jira_oauth.py FIP               # Test metrics collection
python test_jira_basic.py FIP               # Explore project data
```

**Key endpoints**:
- `GET /api/oauth/jira/authorize` - Start OAuth flow (with CSRF state validation)
- `GET /api/oauth/jira/callback` - OAuth callback (validates state parameter)
- `GET /api/oauth/jira/status` - Check token status
- `POST /api/oauth/jira/refresh` - Manual refresh

**API Migration**: Using Atlassian's new `/rest/api/3/search/approximate-count` endpoint (old `/rest/api/3/search` deprecated).

**Database**: OAuth tokens stored in `oauth_tokens` table with automatic refresh (5 min buffer before expiry).

## Project Structure

### Backend (`backend/`)
```
app/
├── api/              # API endpoints
│   ├── auth.py       # Google SSO authentication
│   ├── admin_users.py # User management (admin only)
│   ├── projects.py   # Project CRUD
│   ├── metrics.py    # Metrics CRUD
│   ├── scores.py     # Score calculations
│   ├── collectors.py # Jira/GitHub collection triggers
│   ├── config.py     # Scoring configuration
│   ├── jobs.py       # Background jobs
│   └── slack_admin.py # Slack config, alerts, templates
├── core/             # Core security modules (auth, oauth_state, security_logger, middleware)
├── models/           # SQLAlchemy models
│   ├── user.py       # User model (Google SSO, roles)
│   ├── project.py    # Project model (includes slack_channel_id)
│   ├── metrics.py    # Metrics model
│   ├── job.py        # Background job model
│   ├── slack.py      # Slack models (config, alerts, silences, notifications)
│   └── ...
├── services/
│   ├── calculators/  # Score calculators for 8 dimensions
│   ├── collectors/   # Data collectors
│   │   ├── jira/     # Jira collector
│   │   ├── github/   # GitHub collector
│   │   └── dependabot.py  # Dependabot alerts collector
│   ├── alert_service.py   # Alert template rendering, silence checking
│   ├── slack_service.py   # Slack API wrapper
│   ├── job_service.py     # Background job CRUD operations
│   ├── metrics_service.py # Metrics upsert with manual field sync
│   ├── score_cache.py     # Redis score cache (get/mget/set/invalidate)
│   └── normalizers/  # Metric normalization (raw → 0-1 scale)
├── worker/           # ARQ background worker
│   ├── settings.py   # Worker configuration (Redis, timeouts, cron jobs)
│   ├── tasks.py      # Task definitions (capture_history_task)
│   ├── check_dependabot.py    # Dependabot alerts cron job
│   └── check_business_alerts.py  # Business alerts cron job
├── config.py         # Settings (Pydantic)
├── database.py       # Database connection
└── main.py           # FastAPI app

scripts/              # Utility scripts (generate_jwt_token.py)
tests/                # Pytest tests (~760 total)
    test_integration.py   # Integration tests (scores API, auth, config, collectors)
    test_score_cache.py   # Score cache unit tests (14 tests)
    test_slack_*.py       # Slack-related tests
    test_alert_*.py       # Alert service tests
    test_notifications_*.py  # Notifications API tests
    integration/
        test_scores_batch.py  # Batch scores endpoint tests
```

### Frontend (`frontend/src/`)
```
components/           # React components
  Admin/              # Admin page components
    JobsContent.tsx   # Background + scheduled jobs management
  NotificationsAdmin/ # Notifications admin tab components
    AlertLogTab.tsx   # Sent notifications log with filters
    SilencesTab.tsx   # Per-project alert silencing
    AlertConfigTab.tsx # Enable/disable alerts, edit templates
    StatisticsTab.tsx  # Notification statistics
  ProjectDetail/      # Project page components
    InteractiveTimelineChart.tsx  # Period selector with scores chart
    HistoricalCaptureSection.tsx  # Batch capture UI with progress
    SnapshotManager.tsx           # Container for batch capture + export
  Settings/           # Settings tab components
    ConfigurationTab.tsx # Scoring targets/weights configuration
    SlackTab.tsx       # Slack bot token + leadership channel config
  ui/                 # Reusable UI components (RatingButtons, etc.)
constants/            # Shared constants (dates.ts with MONTHS)
contexts/             # React contexts (AuthContext)
hooks/                # Custom hooks (useProjects, useMetrics, useJobs, etc.)
pages/                # Page components
  Admin.tsx           # Admin page with tabs (Configuration, Slack, Notifications, Jobs)
  Projects.tsx        # Projects list
  ProjectDetail.tsx   # Single project view
  GlobalDashboard.tsx # Cross-project metrics
  Login.tsx           # Login page
services/             # API clients (api.ts with JWT interceptors)
types/                # TypeScript types (auth.ts, index.ts)
utils/                # Utility functions (dateUtils.ts)
```

### Admin Page Structure

The Admin page (`/admin`) consolidates all administrative functions:

| Tab | Description | Sub-tabs |
|-----|-------------|----------|
| Configuration | Scoring targets and weights | - |
| Slack | Bot token, leadership channel, test connection | - |
| Notifications | Alert management | Alert Log, Silences, Alert Config, Statistics |
| Jobs | Background and scheduled jobs | - |

### Infrastructure (`infrastructure/`)
```
infrastructure/
├── bootstrap/              # State storage (S3 + DynamoDB)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── main.tf                 # Provider and backend
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── network.tf              # VPC, subnets, routing
├── security_groups.tf      # Firewall rules
├── ec2.tf                  # EC2 instance + IAM
├── rds.tf                  # PostgreSQL database
├── ecr.tf                  # Container registry
├── secrets.tf              # Secrets Manager
├── iam.tf                  # GitHub OIDC
├── cloudwatch.tf           # Logs and alarms
├── templates/
│   └── user_data.sh        # EC2 bootstrap script
└── environments/
    └── prod.tfvars.example # Production config template
```

### Documentation (`docs/`)
- `OAUTH_SETUP.md` - Jira OAuth 2.0 setup guide
- `SECURITY_QUICK_START.md` - Security quick start (5 min)
- `SECURITY_IMPLEMENTATION.md` - Full security implementation guide
- `DEVELOPMENT_AUTH.md` - Development authentication details
- `SECURITY_MIGRATION_GUIDE.md` - Production migration guide

### Key Dependencies

**Backend**:
- `fastapi` - Web framework
- `sqlalchemy[asyncio]` - Async ORM
- `pydantic-settings` - Configuration management
- `python-jose[cryptography]` - JWT tokens
- `slowapi` - Rate limiting
- `httpx` - Async HTTP client (for Jira/GitHub APIs)
- `itsdangerous` - OAuth state tokens
- `arq` - Async job queue (Redis-backed)
- `redis` - Redis client (ARQ job queue + score cache)

**Frontend**:
- `react` + `typescript` - UI framework
- `react-router-dom` - Routing
- `@tanstack/react-query` - Data fetching
- `tailwindcss` - Styling
- `@react-oauth/google` - Google Sign-In

## Coding Standards

### Python
- Type hints required on all functions
- Use `X | None` not `Optional[X]`
- Use `list[str]` not `List[str]`
- Formatter: Black (88 chars), Linter: Ruff
- Security: Always validate user input, use parameterized queries

### TypeScript
- Strict mode, explicit return types
- Prefer `interface` over `type` for objects
- No `any`—use `unknown` if needed
- Security: Always sanitize user input, handle errors gracefully

## Frontend Patterns

### React Query Keys

**CRITICAL**: Always use centralized query keys from `hooks/queryKeys.ts`. Never use string literals.

```typescript
// ❌ WRONG - magic strings
queryKey: ['projects']
queryKey: ['scores', projectId]

// ✅ CORRECT - typed constants
import { queryKeys } from './queryKeys';
queryKey: queryKeys.projects.all
queryKey: queryKeys.scores.byProject(projectId)
```

Available keys:
- `queryKeys.projects.all` / `.detail(id)`
- `queryKeys.metrics.byProject(projectId)`
- `queryKeys.scores.all` / `.byProject(projectId)` / `.history(projectId, limit)` / `.batch(ids)`
- `queryKeys.config.all` / `.parameters` / `.validation`

### Generic Mutation Hooks

Use factory pattern for similar mutations to avoid duplication:

```typescript
// Generic factory in useMetrics.ts
function useMetricsFieldMutation<T>(
  projectId: string,
  existingMetrics: Metrics | null,
  fieldName: MetricsField,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMetricsMutation<T>(projectId, existingMetrics, fieldName, queryClient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
    },
  });
}

// Usage - creates typed hooks with minimal code
export function useUpdateEVMData(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<EVMData>(projectId, existingMetrics, 'evm_data');
}
```

### Hook Organization

- `useProjects.ts` - Project CRUD operations
- `useMetrics.ts` - Metrics mutations (all field-specific hooks, period-aware)
- `useScores.ts` - Score queries only
- `useProjectScoresMap.ts` - Batch score fetching for projects index (`POST /scores/batch`)
- `useConfig.ts` - Config parameters and validation
- `usePeriodCapture.ts` - **Primary** - `useCapturePeriod` for single period capture (UI "Collect Metrics" button)
- `useJobs.ts` - Background job management (`useCaptureHistoryJob`, `useJobStatus` with polling)
- `useSnapshots.ts` - Metrics history queries (alias: `useProjectSnapshots`)
- `useCollectors.ts` - ⚠️ Legacy - separate Jira/GitHub triggers (use `usePeriodCapture` instead)
- `cacheUtils.ts` - Centralized query invalidation helpers (invalidates batch key on any project data change)

## Key API Endpoints

### Metrics Capture

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects/{id}/capture-period` | POST | **Primary method** - Captures Jira+GitHub metrics for selected period, creates BOTH punctual and cumulative snapshots |
| `/jobs/capture-history` | POST | **Batch capture** - Enqueues background job for date range (multiple months). Returns job ID for polling |
| `/collect/project/{id}/jira` | POST | ⚠️ Legacy - use capture-period instead |
| `/collect/project/{id}/github` | POST | ⚠️ Legacy - use capture-period instead |

### Background Jobs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs/capture-history` | POST | Create batch historical capture job |
| `/jobs/{id}` | GET | Get job status/progress (for polling) |
| `/jobs` | GET | List jobs (filter by project_id, status, type) |
| `/jobs/{id}/cancel` | POST | Cancel pending job |
| `/jobs/{id}/retry` | POST | Retry failed job |

### Metrics & Scores Queries

| Endpoint | Method | Default `snapshot_type` |
|----------|--------|-------------------------|
| `/scores/project/{id}` | GET | cumulative |
| `/scores/project/{id}/history` | GET | cumulative |
| `/scores/batch` | POST | cumulative (request body: `{ project_ids, snapshot_type }`) |
| `/metrics/project/{id}` | GET | cumulative |
| `/metrics/project/{id}/history` | GET | cumulative |
| `/metrics/project/{id}/{year}/{month}` | GET | cumulative |

All GET endpoints accept `?snapshot_type=punctual` to query punctual metrics instead.

**Batch scores** (`POST /scores/batch`): Returns `{ scores: Record<id, ScoreResponse>, errors: Record<id, string> }`. Used by the projects index page to fetch all scores in one request. Accepts up to 50 project IDs. Uses Redis cache for hits, computes and caches misses.

### Slack & Notifications Admin

**All endpoints in this section require admin role.**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/slack/config` | GET | Get Slack config (token masked) |
| `/admin/slack/config` | PUT | Update bot token and/or leadership channel |
| `/admin/slack/test` | POST | Test Slack bot token validity |
| `/admin/slack/channels` | GET | List available Slack channels |
| `/admin/alerts` | GET | List all alert definitions |
| `/admin/alerts/{id}` | PUT | Enable/disable alert, update config |
| `/admin/alerts/{id}/templates` | GET | Get message templates for alert |
| `/admin/alerts/{id}/test` | POST | Send test alert |
| `/admin/templates/{id}` | PUT | Update message template |
| `/notifications` | GET | List sent notifications (with filters) |
| `/notifications/stats` | GET | Get notification statistics |
| `/silences` | GET | List active silences |
| `/silences` | POST | Create a silence |
| `/silences/{id}` | DELETE | Remove a silence |
| `/admin/jobs/scheduled` | GET | List scheduled jobs with last run info |
| `/admin/jobs/scheduled/{name}/run` | POST | Manually trigger a scheduled job |

## Backend Patterns

### Shared Utilities

Common utilities go in dedicated modules to avoid duplication:

```python
# collectors/utils.py - shared across all collectors
def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

# In jira/utils.py or github/utils.py - re-export with domain-specific alias
from app.services.collectors.utils import parse_iso_datetime
parse_jira_datetime = parse_iso_datetime
```
