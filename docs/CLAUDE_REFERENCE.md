# CLAUDE_REFERENCE.md

Detailed reference for subsystems. Consult when working on specific features.

## Authentication & Security

**Status**: Google SSO with domain restriction (`@vizzuality.com`) + JWT in httpOnly cookies.

**Flow:**
1. User clicks "Sign in with Google"
2. Google returns ID token to frontend
3. Frontend sends token to `POST /api/auth/google` with `credentials: 'include'`
4. Backend validates token, checks domain, creates/gets user
5. Backend sets JWT as httpOnly cookie (`access_token`, path `/api`, SameSite=Lax)
6. Response body returns only `{ user }` (no token in body)
7. All subsequent requests include cookie automatically

**JWT Cookie details:**

| Aspect | Detail |
|--------|--------|
| Cookie name | `access_token` |
| Path | `/api` |
| HttpOnly | Yes |
| Secure | `true` in production, `false` when `DEBUG=true` |
| SameSite | `Lax` |
| Max age | `jwt_expire_hours * 3600` (default 24h) |
| CSRF | Not needed (SameSite=Lax + JSON Content-Type + CORS) |

**Token resolution in `get_current_user()`:**
1. Cookie (`request.cookies.get("access_token")`)
2. `Authorization: Bearer` header
3. Dev bypass if `DEBUG=true`

**Frontend auth state:**
- `auth_user` cached in `localStorage` (prevents UI flicker)
- No token in `localStorage` — cookie is httpOnly
- `AuthContextType` has async `logout()`, no `getToken()`
- Axios uses `withCredentials: true`

**Key endpoints:**
- `POST /api/auth/google` - Exchange Google token for JWT cookie
- `POST /api/auth/logout` - Clear cookie
- `GET /api/auth/me` - Validate session
- `GET /api/admin/users` - List users (admin)
- `PATCH /api/admin/users/{id}` - Update role (admin)
- `DELETE /api/admin/users/{id}` - Delete user (admin)

**Dev mode:**
- `DEBUG=true` → CORS allows localhost, `Secure=false`
- `VITE_BYPASS_AUTH=true` → Skip auth entirely (independent of DEBUG)

**Admin-only endpoints** (use `AdminUser` dependency):
- `/admin/users/*`, `/admin/slack/*`, `/admin/alerts/*`, `/admin/templates/*`, `/admin/jobs/*`
- `/notifications/*`, `/silences/*`
- `/global/calculate`, `/global/recalculate`
- `/jobs/capture-history` (POST), `/jobs/{id}/cancel`, `/jobs/{id}/retry`, `/jobs/{id}` (DELETE)

**Admin-only UI**: `/admin` route, admin nav link, Batch Historical Capture, Calculate All/Recalculate buttons.

### OAuth 2.0 (Jira)

Jira collector uses OAuth 2.0 with classic scopes: `read:jira-work read:jira-user`.

Setup: `docs/OAUTH_SETUP.md`

**Endpoints:**
- `GET /api/oauth/jira/authorize` - Start flow (CSRF state)
- `GET /api/oauth/jira/callback` - Callback (validates state)
- `GET /api/oauth/jira/status` - Token status
- `POST /api/oauth/jira/refresh` - Manual refresh

Tokens stored in `oauth_tokens` table with auto-refresh (5 min buffer).

## Slack Notifications System

Automated alerts to Slack channels for business and security issues.

**Architecture:**
- **Business alerts** → Leadership channel (budget exceeded, timeline at risk, project overdue)
- **Project alerts** → Per-project channels (Dependabot vulnerabilities)

**Database tables:** `slack_config`, `alert_definitions`, `message_templates`, `alert_silences`, `alert_notifications`, `dependabot_alerts_tracked`, `scheduled_job_runs`

**Scheduled jobs (ARQ cron):**
- `check_dependabot_alerts` - Daily 8:00 UTC
- `check_business_alerts` - Daily 9:00 UTC

**Dependabot strategy:**

| Situation | Action |
|-----------|--------|
| Not tracked | Notify + track |
| Already tracked | Skip |
| Critical unresolved > 2 days | Reminder |
| High unresolved > 7 days | Reminder |
| Disappears from GitHub | Mark resolved |

Template variables: `{project_name}`, `{vuln_severity}`, `{vuln_package}`, `{vuln_cve}`, `{vuln_url}`, `{vuln_age_days}`

**Business alerts:** Monthly throttling per project. Types: `budget_exceeded` (>=100%), `timeline_at_risk` (velocity-based), `project_overdue` (>30 days past end_date).

**Key services:**
- `app/services/slack_service.py` - Slack API wrapper
- `app/services/alert_service.py` - Template rendering, silence checking
- `app/services/collectors/dependabot.py` - Fetch Dependabot alerts

## Background Jobs (ARQ + Redis)

```
Frontend → POST /jobs/capture-history → Job record → Redis → ARQ Worker
                                           ↓
                                  Frontend polls GET /jobs/{id}
```

**Status flow:** `PENDING → RUNNING → COMPLETED/FAILED`, also `CANCELLED`

**Key files:**
- `app/worker/settings.py` - Config (timeouts, retries, Redis)
- `app/worker/tasks.py` - Task definitions
- `app/models/job.py` - Job model
- `app/services/job_service.py` - CRUD
- `app/api/jobs.py` - REST endpoints

**Design decisions:**
- Jobs tracked in PostgreSQL (not just Redis)
- 5-second delay between months to avoid rate limiting
- Frontend persists active job IDs in localStorage

## Redis Score Cache

Scores cached in Redis to avoid N+1 on projects index. **Optional** — falls back to on-demand if Redis unavailable.

**Key:** `scores:latest:{project_id}:{snapshot_type}`

**Strategy:**

| Event | Action |
|-------|--------|
| `GET /scores/project/{id}` (latest) | Read-through: cache → compute on miss → cache |
| `POST /scores/batch` | MGET → compute misses → SET misses |
| `POST /projects/{id}/capture-period` | Write-through: cache both snapshot types |
| Metrics create/delete | Invalidate project keys |
| Config update | Invalidate ALL (`SCAN + delete scores:latest:*`) |
| Worker batch capture | Invalidate after each month |

**TTL:** 1 hour. Invalidation is primary freshness mechanism.

**Dependency:** `OptionalScoreCache` is `ScoreCacheService | None`. Always guard: `if cache: await cache.invalidate(...)`.

**Frontend:** Projects index uses `POST /scores/batch` via `useProjectScoresMap`. Batch key invalidated by `invalidateProjectData()` in `cacheUtils.ts`.

## Production Deployment (AWS)

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

| Service | Type | Purpose |
|---------|------|---------|
| ALB | - | HTTPS + path routing |
| EC2 | t3.micro | Docker host |
| RDS | db.t4g.small | PostgreSQL 16 |
| ECR | - | Container registry |
| Secrets Manager | - | Credentials |
| SSM | - | Secure shell (no SSH) |

**CI/CD:** Push to main → CI Tests → Build → Push ECR → SSM Deploy → Health Check

**AWS Access:** Profile `vizzhub`, Region `eu-west-3`, EC2 `i-097d6d92ab30d9622`

**Operations:**
```bash
# SSM session
aws ssm start-session --profile vizzhub --region eu-west-3 --target i-097d6d92ab30d9622

# Non-interactive commands
aws ssm send-command --profile vizzhub --region eu-west-3 \
  --instance-ids "i-097d6d92ab30d9622" \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["docker ps"]}'

# Manual deploy
cd /opt/hub
export TAG="<sha>" ECR_URI="<account>.dkr.ecr.eu-west-3.amazonaws.com"
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin $ECR_URI
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d

# Refresh secrets
/opt/hub/fetch-secrets.sh
docker compose -f /opt/hub/docker-compose.prod.yml restart backend worker
```

**Infrastructure:** `cd infrastructure && tofu plan -var-file=environments/prod.tfvars`

## Key API Endpoints

### Projects

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects` | GET | Paginated list. Params: `page`, `page_size` (45), `search`, `status`, `sort` (`name`/`created_at`/`status`), `order`, `start_date_from/to` |
| `/projects?lightweight=true` | GET | `[{id, name}]` for dropdowns (no pagination) |
| `/projects/{id}` | GET | Single project |
| `/projects` | POST | Create |
| `/projects/{id}` | PATCH | Partial update |
| `/projects/{id}` | PUT | Full replacement |
| `/projects/{id}` | DELETE | Delete |

Response: `{ items, total, page, page_size, pages }`

### Metrics Capture

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects/{id}/capture-period` | POST | **Primary** - Jira+GitHub, creates both snapshot types |
| `/jobs/capture-history` | POST | Batch background job |
| `/collect/project/{id}/jira` | POST | Legacy |
| `/collect/project/{id}/github` | POST | Legacy |

### Metrics & Scores

| Endpoint | Method | Default snapshot_type |
|----------|--------|----------------------|
| `/scores/project/{id}` | GET | cumulative |
| `/scores/project/{id}/history` | GET | cumulative |
| `/scores/batch` | POST | cumulative (`{ project_ids, snapshot_type }`) |
| `/metrics/project/{id}` | GET | cumulative |
| `/metrics/project/{id}/history` | GET | cumulative |
| `/metrics/project/{id}/{year}/{month}` | GET | cumulative |

All accept `?snapshot_type=punctual`.

Batch: `{ scores: Record<id, ScoreResponse>, errors: Record<id, string> }`, max 50 IDs.

### Slack & Notifications (admin only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/slack/config` | GET/PUT | Slack config |
| `/admin/slack/test` | POST | Test connection |
| `/admin/slack/channels` | GET | List channels |
| `/admin/alerts` | GET | List alerts |
| `/admin/alerts/{id}` | PUT | Update alert |
| `/admin/alerts/{id}/templates` | GET | Get templates |
| `/admin/alerts/{id}/test` | POST | Test alert |
| `/admin/templates/{id}` | PUT | Update template |
| `/notifications` | GET | Notification log |
| `/notifications/stats` | GET | Stats |
| `/silences` | GET/POST | List/create silences |
| `/silences/{id}` | DELETE | Remove silence |
| `/admin/jobs/scheduled` | GET | Scheduled jobs |
| `/admin/jobs/scheduled/{name}/run` | POST | Trigger job |
