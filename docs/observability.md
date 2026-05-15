# Observability

## Architecture

```
App / Worker
├─ Logs (JSON) ──▶ Grafana Alloy ──▶ Grafana Cloud Loki
├─ Metrics ──────▶ Grafana Alloy ──▶ Grafana Cloud Prometheus
├─ Errors ───────▶ Sentry
└─ Health (/health/live, /health/ready)
```

## Components

| Component | What | Where |
|-----------|------|-------|
| **Structured logging** | JSON logs with request_id, service, environment, release | All backend + worker modules via structlog |
| **Request ID** | UUID per request, propagated via X-Request-ID header | Middleware, bound to logs + Sentry context |
| **Sentry (backend)** | Errors, performance traces (20% sample) | [sentry.io](https://sentry.io) — project `vizzhub-backend` |
| **Sentry (frontend)** | Errors, Web Vitals, route-level tracing | [sentry.io](https://sentry.io) — project `vizzhub-frontend` |
| **Prometheus metrics** | HTTP request count/latency/size, worker job count/duration | `GET /metrics` |
| **Grafana Alloy** | Scrapes `/metrics` → Prometheus, collects Docker logs → Loki | Container `hub-alloy` on EC2 |
| **Grafana Cloud** | Dashboards, metrics (Prometheus), logs (Loki) | [vizzhub.grafana.net](https://vizzhub.grafana.net) |
| **Health checks** | Liveness + readiness (DB, Redis, worker heartbeat) | `GET /health/live`, `GET /health/ready` |
| **CloudWatch Logs** | Backend → `/hub/backend`, Worker → `/hub/worker` (backup) | AWS Console > CloudWatch > Log groups |

## Health Checks

```bash
# Liveness (process running)
curl https://hub.vizzuality.com/health/live

# Readiness (dependencies healthy)
curl https://hub.vizzuality.com/health/ready
```

Readiness checks: database (SELECT 1, 5s timeout), Redis (PING, 2s timeout), worker heartbeat (Redis key with 120s TTL).

## Log Format

Production logs are JSON:

```json
{
  "event": "request_completed",
  "level": "info",
  "service": "vizzhub-backend",
  "environment": "production",
  "release": "abc123",
  "request_id": "uuid-here",
  "timestamp": "2026-03-29T14:30:00Z"
}
```

All events follow `{entity}_{action}` naming (e.g., `job_started`, `auth_login_failed`, `alert_sent`).

Development uses console renderer (colored, human-readable).

## CloudWatch Queries

```
# Errors in last hour
fields @timestamp, event, request_id, @message
| filter level = "error"
| sort @timestamp desc

# Slow requests (>1s)
fields @timestamp, request_id, path, duration_ms
| filter duration_ms > 1000
| sort duration_ms desc

# Trace a request
fields @timestamp, event, @message
| filter request_id = "uuid-here"
| sort @timestamp asc
```

## Grafana Dashboard

**URL:** [vizzhub.grafana.net](https://vizzhub.grafana.net) → Dashboards → "VizzHub Overview"

Sections:
- **Application (HTTP)** — request rate, latency P95/P50, error rate (5xx), status codes
- **Worker** — jobs completed (last 1h), job duration P95/P50, backend up/down
- **Logs** — error log stream, log volume by level

Dashboard JSON is version-controlled at `infrastructure/grafana-dashboard.json`.

## Incident Flow

1. **Error** → Sentry alert → stack trace → use `request_id` to find full logs in Grafana (Loki)
2. **Performance** → Grafana dashboard shows latency spike → identify endpoint → Loki logs for details → Sentry for traces
3. **System** → `/health/ready` returns 503 → check which dependency is unhealthy → Grafana logs for context

## Environment Variables

### Backend (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | *(empty)* | Sentry DSN — empty disables Sentry |
| `LOG_FORMAT` | `console` | `json` for production, `console` for dev |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `APP_ENV` | `development` | Environment tag for logs and Sentry |
| `RELEASE` | *(empty)* | Git SHA — set automatically in deploy |

### Frontend (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_SENTRY_DSN` | *(empty)* | Frontend Sentry DSN — empty disables |
| `VITE_APP_ENV` | `development` | Environment tag |
| `VITE_RELEASE` | *(empty)* | Git SHA for source map correlation |

## Grafana Alloy

Alloy runs as a Docker container (`hub-alloy`) on EC2. Config at `infrastructure/alloy-config.alloy`.

- Scrapes `backend:8000/metrics` every 30s → remote_write to Grafana Cloud Prometheus
- Collects Docker logs from `hub-backend` and `hub-worker` → push to Grafana Cloud Loki
- Credentials in AWS Secrets Manager (`/hub/prod/grafana-cloud`), injected via `.env.alloy`

## Alerting

### Grafana Cloud Alert Rules

Alert rules configured in Grafana Cloud (folder "VizzHub"):

| Rule | Condition | Severity |
|------|-----------|----------|
| **Backend Down** | No metrics scraped for 2+ min | Critical |
| **High Error Rate** | 5xx rate exceeds threshold | Warning |
| **High Latency P95** | P95 latency exceeds threshold | Warning |
| **MCP Permission Denied** | Any `mcp_permission_denied` log line in 5m | Warning |

Contact point: Slack `#vizzhub` channel (bot token).

#### MCP Permission Denied — paste-ready spec

When the `@mcp_requires` decorator rejects a tool call, the backend
emits a `warning`-level structlog event `mcp_permission_denied`. In
normal operation this should be **zero** — either an LLM agent is
calling tools beyond its scope, or someone is probing the MCP surface
with a token that lacks the right permissions. Either way: investigate.

**Datasource:** `grafanacloud-vizzhub-logs` (Loki, UID `grafanacloud-logs`).

**LogQL query (Loki):**

```logql
sum by (tool, user_email) (
  count_over_time(
    {service="backend"}
    | json
    | event = `mcp_permission_denied`
    [5m]
  )
)
```

**Rule config:**

- **Folder:** VizzHub
- **Group:** Security
- **Evaluation:** every 1m, for 0m (fire on first occurrence)
- **Threshold:** `is above 0`
- **Severity label:** `warning`
- **Summary:** `MCP permission denied for {{ $labels.tool }}`
- **Description:** `User {{ $labels.user_email }} was denied access to MCP tool {{ $labels.tool }}. Check logs and verify whether the caller's permissions are correct or whether an LLM agent is over-reaching.`
- **Contact point:** Slack `#vizzhub`

**Runbook on fire:**

1. Open Loki, filter `{service="backend"} | json | event="mcp_permission_denied"` for the last 1h.
2. Identify `user_email` and `tool` — is this a known user/agent or unknown caller?
3. If known: confirm whether their role should grant the listed `permission`. If yes, fix role assignment. If no, the gate worked — the agent prompt needs adjusting, not the role.
4. If unknown email: rotate any leaked tokens, check `mcp_server/auth/token_verifier.py` for the issuer claim. Treat as a security incident.

Two upstream files matter here: `mcp_server/auth/permissions.py` (emits the
event) and `mcp_server/data/base.py` (`McpUserContext` shape).

### Sentry Alerts

Sentry alerts route to Slack via Sentry's native Slack integration (configured in Sentry UI, not in code).
