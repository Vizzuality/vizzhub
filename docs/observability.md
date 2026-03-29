# Observability

## Architecture

```
App / Worker
├─ Logs (JSON) ─────────────▶ CloudWatch Logs
├─ Metrics ─────────────────▶ /metrics (Prometheus format)
├─ Errors & Performance ───▶ Sentry
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
| **Health checks** | Liveness + readiness (DB, Redis, worker heartbeat) | `GET /health/live`, `GET /health/ready` |
| **CloudWatch Logs** | Backend → `/hub/backend`, Worker → `/hub/worker` | AWS Console > CloudWatch > Log groups |

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

## Incident Flow

1. **Error** → Sentry alert → investigate stack trace → use `request_id` to find full logs in CloudWatch
2. **Performance** → `/metrics` shows latency spike → identify endpoint → CloudWatch logs for details → Sentry for traces
3. **System** → `/health/ready` returns 503 → check which dependency is unhealthy → CloudWatch for context

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

## Pending

- Grafana Cloud dashboard (metrics visualization)
- Grafana Alloy (metrics scraping + remote_write)
- Sentry alerts → Slack
- Grafana alert rules (error rate, latency, queue depth)

See [observability_plan.md](observability_plan.md) for the full implementation plan.
