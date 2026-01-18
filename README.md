# Project Scorecard

A modern web application for evaluating software development projects across 8 dimensions. Migrated from Google Sheets + Google Apps Script to FastAPI + React.

## Dimensions

| Dimension | Code | Focus |
|-----------|------|-------|
| Delivery Timeliness | P_time | Schedule adherence (SPI + milestones) |
| Cost Control | P_cost | Budget discipline (CPI + variance) |
| Product Quality | P_quality | Defects, governance, reviews |
| Strategic Value | P_value | OKR impact |
| Client Satisfaction | P_satisfaction | Survey + PM estimation |
| Flow & Predictability | P_flow | Lead time, efficiency, commitment |
| Engineering Maturity | P_engineering | Testing, reviews, architecture |
| Risk Posture | P_risk | Security, code review |

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Manual Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run development server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## Project Structure

```
project-scorecard/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Exceptions, utilities
│   │   ├── models/         # Pydantic + SQLAlchemy models
│   │   └── services/
│   │       ├── collectors/ # Jira/GitHub data collection
│   │       ├── normalizers/# Metric normalization
│   │       └── calculators/# Score computation
│   ├── tests/              # pytest tests
│   ├── alembic/            # Database migrations
│   └── scoring_config.yaml # Weights and targets
├── frontend/               # React + TypeScript
│   └── src/
│       ├── components/     # React components
│       ├── hooks/          # Custom hooks
│       ├── pages/          # Page components
│       ├── services/       # API client
│       └── types/          # TypeScript types
├── docs/
│   ├── MIGRATION_PLAN.md   # Legacy → new mapping
│   └── API.md              # API documentation
├── legacy/                 # Original system docs
└── docker-compose.yml
```

## Configuration

### Scoring Configuration

Edit `backend/scoring_config.yaml` to adjust:

- **Targets**: Values against which metrics are normalized
- **Weights**: How much each component contributes to dimension scores
- **Constants**: System constants like Sev1 cap and grace days

```yaml
targets:
  defect_density: 3      # defects per 100 tasks
  escaped_rate: 0.01     # escapes per 100 tasks
  mttr_hours: 24         # mean time to recover
  # ...

weights:
  global:
    time: 0.12
    cost: 0.10
    quality: 0.18
    # ...
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard

# API Keys (for collectors)
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token

GITHUB_TOKEN=your-github-token
```

## API Usage

### Create a Project

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "jira_project_key": "PROJ", "github_repo": "org/repo"}'
```

### Add Metrics

```bash
curl -X POST http://localhost:8000/api/metrics/project/{project_id} \
  -H "Content-Type: application/json" \
  -d '{
    "period_start": "2024-01-01",
    "period_end": "2024-01-31",
    "evm_data": {
      "budget_total": 100000,
      "cost_to_date": 45000,
      "percent_completed": 0.5,
      "percent_planned": 0.5
    }
  }'
```

### Get Scores

```bash
curl http://localhost:8000/api/scores/project/{project_id}
```

## Testing

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_calculators.py
```

## Design Principles

1. **Scripts only collect** → calculators decide meaning
2. **All ratios normalized to 0-1** before weighting
3. **Neutral (0.5) only when data genuinely unavailable**
4. **Penalize** when governance tools are disabled
5. **Weights must sum to 1** within each group
6. **Inverted normalization** for "lower is better" metrics

## Documentation

- [Migration Plan](docs/MIGRATION_PLAN.md) - Legacy to new system mapping
- [API Documentation](docs/API.md) - REST API reference
- [Legacy Documentation](legacy/README.md) - Original system docs

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.0 (async)
- Pydantic v2
- pytest

### Frontend
- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Query
- Recharts
- React Hook Form

## License

MIT
