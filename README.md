[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Vizzuality_vizzhub&metric=alert_status&token=811581c16b7bc79cd92bc6a63ddd87cfe028dbfc)](https://sonarcloud.io/summary/new_code?id=Vizzuality_vizzhub)

# vizzhub

Internal platform for project health visibility at Vizzuality. Multi-module architecture with two active modules:

- **Scorecard** — Evaluates software projects across 8 dimensions (delivery, cost, quality, value, satisfaction, flow, engineering, risk) with automated Jira/GitHub data collection, scoring, and dashboards.
- **ISO 27001** — Periodic access reviews for ISO 27001 Annex A.9 compliance. Captures Google Workspace snapshots, detects changes, supports reviewer sign-off, and exports to XLSX.

## Quick Start

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js 18+** and npm (frontend)
- **PostgreSQL 16** (database)
- **Redis** (optional, for score caching and background jobs)

### 1. Database Setup

```bash
brew install postgresql@16
brew services start postgresql@16

psql postgres
CREATE DATABASE scorecard;
CREATE USER scorecard WITH PASSWORD 'scorecard';
GRANT ALL PRIVILEGES ON DATABASE scorecard TO scorecard;
\q
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — see Environment Variables below

python run_server.py
```

Backend runs on **http://localhost:8000** (API docs at `/docs`)

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on **http://localhost:5173**

### 4. Worker (optional, for background jobs)

```bash
cd backend
arq app.worker.settings.WorkerSettings
```

### Docker Compose (Alternative)

```bash
docker-compose up -d
docker-compose logs -f backend
```

### Development Mode

- Backend: `DEBUG=true` — authentication bypassed
- Frontend: `BYPASS_AUTH=true` — no login required

## Project Structure

```
vizzhub/
├── backend/app/
│   ├── core/                  # Auth, projects, users, jobs, OAuth, shared services
│   │   ├── api/               # Core API routers (auth, projects, admin, jobs, oauth)
│   │   ├── models/            # Project, User, Job, OAuthToken, IntegrationSetting
│   │   └── services/          # oauth_service, job_service, integration_token_service
│   ├── modules/
│   │   ├── scorecard/         # Scoring engine, collectors, calculators, export
│   │   └── iso/               # Access snapshots, reviews, Google Workspace collector
│   ├── worker/                # ARQ background tasks
│   └── main.py
├── frontend/src/
│   ├── core/                  # Auth, layout, shared hooks/services/types
│   ├── modules/
│   │   ├── scorecard/         # Dashboard, project detail, settings, metrics
│   │   └── iso/               # Snapshots, reviews, config
│   └── shared/                # UI components (shadcn), theme, constants
├── infrastructure/            # Terraform (AWS)
└── docs/
```

## Scorecard Dimensions

| Dimension             | Code           | Focus                                 |
| --------------------- | -------------- | ------------------------------------- |
| Delivery Timeliness   | P_time         | Schedule adherence (SPI + milestones) |
| Cost Control          | P_cost         | Budget discipline (CPI + variance)    |
| Product Quality       | P_quality      | Defects, governance, reviews          |
| Strategic Value       | P_value        | OKR impact                            |
| Client Satisfaction   | P_satisfaction | Survey + PM estimation                |
| Flow & Predictability | P_flow         | Lead time, efficiency, commitment     |
| Engineering Maturity  | P_engineering  | Testing, reviews, architecture        |
| Risk Posture          | P_risk         | Security, code review                 |

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard

# Security (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=your-secret-key
SESSION_SECRET_KEY=your-session-secret

# Application
DEBUG=true
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Jira OAuth 2.0 (see docs/OAUTH_SETUP.md)
JIRA_OAUTH_CLIENT_ID=
JIRA_OAUTH_CLIENT_SECRET=
JIRA_OAUTH_REDIRECT_URI=http://localhost:8000/api/oauth/jira/callback

# GitHub (fine-grained PAT with pull_requests=read)
GITHUB_TOKEN=

# Google OAuth (for auth + ISO module)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Redis (optional)
REDIS_URL=redis://localhost:6379
```

## Testing

**Backend: ~970 tests | Frontend: ~340 tests**

```bash
# Backend
cd backend
export TEST_DATABASE_URL="postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test"
pytest                    # All tests
pytest -x                 # Stop on first failure
pytest --cov=app          # With coverage

# Frontend
cd frontend
npm test -- --run         # Run once
npm run test:coverage     # With coverage
```

## Git Workflow

| Branch      | Purpose                              |
| ----------- | ------------------------------------ |
| `main`      | Production-ready code, releases only |
| `dev`       | Active development (default branch)  |
| `feature/*` | Feature branches, PR to `dev`        |

## Documentation

- [API Reference](docs/API.md)
- [OAuth 2.0 Setup](docs/OAUTH_SETUP.md)
- [Security Implementation](docs/SECURITY_IMPLEMENTATION.md)
- [Development Auth](docs/DEVELOPMENT_AUTH.md)
- [Testing Guide](docs/TESTING.md)
- [Multi-module Architecture](docs/tracker_integration.md)

## Tech Stack

**Backend:** Python 3.11+, FastAPI, PostgreSQL 16, SQLAlchemy 2.0 (async), Pydantic v2, ARQ (workers), Redis

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Query, Recharts

**Infrastructure:** AWS (EC2, RDS, ALB, ECR), Terraform, GitHub Actions CI/CD

## License

MIT
