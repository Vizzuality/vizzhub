[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Vizzuality_vizzhub&metric=alert_status&token=811581c16b7bc79cd92bc6a63ddd87cfe028dbfc)](https://sonarcloud.io/summary/new_code?id=Vizzuality_vizzhub)

# vizzhub

Internal tracking platform.

## Setup

### Prerequisites

- Python 3.11+, Node.js 18+, PostgreSQL 16, Redis (optional)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit as needed
python run_server.py  # http://localhost:8000, docs at /docs
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
arq app.worker.settings.WorkerSettings
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

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Production |
| `dev` | Active development |
| `feature/*` | PRs to `dev` |

## License

MIT
