[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Vizzuality_vizzhub&metric=alert_status&token=811581c16b7bc79cd92bc6a63ddd87cfe028dbfc)](https://sonarcloud.io/summary/new_code?id=Vizzuality_vizzhub)

# vizzhub

Internal tracking platform.

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python toolchain), Node.js 18+, PostgreSQL 16, Redis (optional). uv installs the right Python automatically.

### Backend

```bash
cd backend
uv sync                 # installs Python 3.13 + all deps from uv.lock
cp .env.example .env    # edit as needed
uv run python run_server.py  # http://localhost:8000, docs at /docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Worker (background jobs)

```bash
cd backend
uv run arq app.worker.settings.WorkerSettings
```

### Docker alternative

```bash
docker-compose up -d
```

### Dev mode shortcuts

- `DEBUG=true` (backend) — auth bypassed
- `BYPASS_AUTH=true` (frontend) — no login required

## Stack

- **Backend:** FastAPI, PostgreSQL 16, SQLAlchemy 2.0 (async), ARQ, Redis
- **Frontend:** React 18, TypeScript, Vite, Tailwind, shadcn/ui, React Query, Recharts
- **Infra:** AWS (EC2, RDS, ALB, ECR), Terraform, GitHub Actions
- **Observability:** structlog, Sentry, Prometheus metrics, CloudWatch Logs — [details](docs/observability.md)

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Production |
| `dev` | Active development |
| `feature/*` | PRs to `dev` |

## License

Copyright (c) 2026 Vizzuality. All rights reserved. See [LICENSE.md](LICENSE.md).
