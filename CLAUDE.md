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
pytest                                        # All backend tests (520 total)
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
npm test         # Run tests (214 total)

# Theme (shadcn/tweakcn)
# Current theme: https://tweakcn.com/r/themes/cmkliqxix000d04la3624132s
# To regenerate theme CSS:
pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/cmkliqxix000d04la3624132s
# Theme uses OKLCH color space, Outfit font (sans), Fira Code font (mono)
```

## Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code, builds/releases only |
| `dev` | Active development (default branch) |
| `feature/*` | Feature branches → PR to `dev` |

- All PRs target `dev` by default
- Merge `dev` → `main` only for releases
- Delete feature branches after merge

## Architecture

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

- Scores are computed on-the-fly, not stored (ensures config changes apply immediately)
- Sev1 incidents cap P_quality at 60 points
- Milestones have a grace period (default 3 days)
- Disabled governance tools get penalized (score = 0), not neutral
- **Metrics consolidation**: Multiple metrics records with same `period_end` are consolidated (`_consolidate_metrics` in `app/api/scores.py`). This handles multiple collector runs creating separate records.
- **Ideals for ratio metrics**: SPI/CPI use ideal=1.0 for scoring; value/ideal gives accurate percentage

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

**Status**: Full security implementation with JWT authentication + OAuth 2.0 for Jira.

#### Development Mode (Current)
- `DEBUG=true` in `.env` → Authentication bypassed for development
- Backend accepts requests without JWT tokens
- Frontend `BYPASS_AUTH=true` → No login required
- Security warnings logged for every bypass

#### Production Mode (Future)
- Google OAuth (Google Sign-In) for company domain users only
- JWT tokens required for all API endpoints (except `/health` and OAuth callbacks)
- Rate limiting active on all endpoints
- Full security headers (HSTS, CSP, X-Frame-Options, etc.)

**See**:
- `docs/SECURITY_QUICK_START.md` - 5-minute security guide
- `docs/DEVELOPMENT_AUTH.md` - Development authentication details
- `audits/security.md` - Complete security audit report

#### Security Features Implemented
- ✅ JWT authentication system
- ✅ OAuth CSRF protection (state parameter validation)
- ✅ Rate limiting (slowapi)
- ✅ Security headers middleware
- ✅ Input validation (JQL injection prevention, UUID validation)
- ✅ Security logging (structured JSON)
- ✅ Error message sanitization

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
│   ├── projects.py   # Project CRUD
│   ├── metrics.py    # Metrics CRUD
│   ├── scores.py     # Score calculations
│   ├── collectors.py # Jira/GitHub collection triggers
│   ├── config.py     # Scoring configuration
│   ├── jobs.py       # Background jobs
│   ├── slack_admin.py # Slack config, alerts, templates, silences, notifications
│   └── schemas/      # Pydantic schemas
│       └── slack.py  # Slack-related schemas
├── core/             # Core security modules (auth, oauth_state, security_logger, middleware)
├── models/           # SQLAlchemy models
│   ├── project.py    # Project model (includes slack_channel_id)
│   ├── metrics.py    # Metrics model
│   ├── job.py        # Background job model
│   ├── slack.py      # Slack models (config, alerts, silences, notifications, etc.)
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
tests/                # Pytest tests (~750 total)
    test_integration.py   # Integration tests (scores API, auth, config, collectors)
    test_slack_*.py       # Slack-related tests
    test_alert_*.py       # Alert service tests
    test_notifications_*.py  # Notifications API tests
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
- `redis` - Redis client for ARQ

**Frontend**:
- `react` + `typescript` - UI framework
- `react-router-dom` - Routing
- `@tanstack/react-query` - Data fetching
- `tailwindcss` - Styling
- Future: `@react-oauth/google` - Google Sign-In (when implemented)

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
- `queryKeys.scores.all` / `.byProject(projectId)` / `.history(projectId, limit)`
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
- `useConfig.ts` - Config parameters and validation
- `usePeriodCapture.ts` - **Primary** - `useCapturePeriod` for single period capture (UI "Collect Metrics" button)
- `useJobs.ts` - Background job management (`useCaptureHistoryJob`, `useJobStatus` with polling)
- `useSnapshots.ts` - Metrics history queries (alias: `useProjectSnapshots`)
- `useCollectors.ts` - ⚠️ Legacy - separate Jira/GitHub triggers (use `usePeriodCapture` instead)

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
| `/jobs/` | GET | List jobs (filter by project_id, status, type) |
| `/jobs/{id}/cancel` | POST | Cancel pending job |
| `/jobs/{id}/retry` | POST | Retry failed job |

### Metrics & Scores Queries

| Endpoint | Method | Default `snapshot_type` |
|----------|--------|-------------------------|
| `/scores/project/{id}` | GET | cumulative |
| `/scores/project/{id}/history` | GET | cumulative |
| `/metrics/project/{id}` | GET | cumulative |
| `/metrics/project/{id}/history` | GET | cumulative |
| `/metrics/project/{id}/{year}/{month}` | GET | cumulative |

All endpoints accept `?snapshot_type=punctual` to query punctual metrics instead.

### Slack & Notifications Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/slack/config` | GET | Get Slack config (token masked) |
| `/admin/slack/config` | PUT | Update bot token and/or leadership channel |
| `/admin/slack/test` | POST | Test Slack bot token validity |
| `/admin/slack/channels` | GET | List available Slack channels |
| `/admin/alerts/` | GET | List all alert definitions |
| `/admin/alerts/{id}` | PUT | Enable/disable alert, update config |
| `/admin/alerts/{id}/templates` | GET | Get message templates for alert |
| `/admin/alerts/{id}/test` | POST | Send test alert |
| `/admin/templates/{id}` | PUT | Update message template |
| `/notifications/` | GET | List sent notifications (with filters) |
| `/notifications/stats` | GET | Get notification statistics |
| `/silences/` | GET | List active silences |
| `/silences/` | POST | Create a silence |
| `/silences/{id}` | DELETE | Remove a silence |
| `/scheduled-jobs/` | GET | List scheduled jobs with last run info |
| `/scheduled-jobs/{name}/trigger` | POST | Manually trigger a scheduled job |

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
