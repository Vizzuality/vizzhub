# Project Scorecard

[![CI](https://github.com/Vizzuality/project-score-card/actions/workflows/ci.yml/badge.svg)](https://github.com/Vizzuality/project-score-card/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/CV-Gate/1f6326035ddb65fccc95e6c0214d7265/raw/coverage.json)

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

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js 18+** and npm (frontend)
- **PostgreSQL 16** (database)

### Local Development (Recommended)

#### 1. Database Setup

```bash
# Install and start PostgreSQL
# macOS (Homebrew):
brew install postgresql@16
brew services start postgresql@16

# Create database and user
psql postgres
CREATE DATABASE scorecard;
CREATE USER scorecard WITH PASSWORD 'scorecard';
GRANT ALL PRIVILEGES ON DATABASE scorecard TO scorecard;
\q
```

#### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set:
# - DATABASE_URL=postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard
# - JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
# - SESSION_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">

# Run database migrations (if any)
# alembic upgrade head

# Start backend server
python run_server.py
```

Backend will run on **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

#### 3. Frontend Setup

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will run on **http://localhost:5173**

### Using Docker Compose (Alternative)

```bash
# Start all services (PostgreSQL, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

### Development Mode

The application runs in **development mode** by default:
- Backend: `DEBUG=true` → Authentication bypassed (no JWT required)
- Frontend: `BYPASS_AUTH=true` → No login required

For production deployment, see `docs/SECURITY_IMPLEMENTATION.md` and `docs/SECURITY_MIGRATION_GUIDE.md`.

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

# Security (REQUIRED - Generate secure random keys)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-secret-key-here
SESSION_SECRET_KEY=your-session-secret-here

# Application
DEBUG=true                    # Set to false in production
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Jira Authentication - Option 1: OAuth 2.0 (Recommended)
# See docs/OAUTH_SETUP.md for detailed setup instructions
JIRA_OAUTH_CLIENT_ID=your-client-id
JIRA_OAUTH_CLIENT_SECRET=your-client-secret
JIRA_OAUTH_REDIRECT_URI=http://localhost:8000/api/oauth/jira/callback
# Classic scopes (recommended by Atlassian):
JIRA_OAUTH_SCOPES=read:jira-work read:jira-user

# Jira Authentication - Option 2: API Token (Fallback)
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token

# GitHub
GITHUB_TOKEN=your-github-token
```

**Important Notes:**
- **Security Keys**: Generate random keys for production. Never commit real keys to git.
- **OAuth 2.0** (Recommended): More secure, automatic token refresh, CSRF protection. See [`docs/OAUTH_SETUP.md`](docs/OAUTH_SETUP.md)
- **Classic Scopes**: Use Atlassian's classic scopes (`read:jira-work read:jira-user`) instead of granular scopes
- **Development Mode**: `DEBUG=true` disables authentication for local development

## Security & Authentication

### Current State (Development)

The application is configured for **development mode**:
- **Backend**: JWT authentication implemented but bypassed when `DEBUG=true`
- **Frontend**: Auth infrastructure ready but `BYPASS_AUTH=true` for development
- **Security**: Full security implementation active (rate limiting, CSRF protection, security headers, input validation)

### Future: Google OAuth

Google OAuth implementation is planned. See [docs/TODO.md](docs/TODO.md) for details.

Implementation guides:
- `docs/SECURITY_QUICK_START.md` - Quick start guide
- `docs/DEVELOPMENT_AUTH.md` - Development authentication details
- `docs/SECURITY_IMPLEMENTATION.md` - Full security implementation

### Security Features

✅ **Implemented**:
- JWT authentication system (production-ready)
- OAuth 2.0 for Jira with CSRF protection
- Rate limiting on all endpoints
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Input validation (JQL injection prevention, UUID validation)
- Structured security logging (JSON format)
- Error message sanitization

📋 **Security Audit**: See `audits/security.md` for complete security audit report (12 vulnerabilities fixed)

## API Usage

### Development Mode (No Auth Required)

```bash
# Create a Project
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "jira_project_key": "PROJ", "github_repo": "org/repo"}'

# Collect Metrics (Jira + GitHub, creates both snapshot types)
curl -X POST http://localhost:8000/api/projects/{project_id}/capture-period \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Get Scores
curl http://localhost:8000/api/scores/project/{project_id}
```

### Production Mode (Auth Required)

```bash
# Generate a JWT token
cd backend
python scripts/generate_jwt_token.py --user-id "user@company.com" --roles "user"

# Use token in API calls
curl -H "Authorization: Bearer <your-jwt-token>" \
  http://localhost:8000/api/projects
```

## Testing

**Total: 312 tests (100% passing) | Coverage: ~85%**

### Backend Tests

```bash
cd backend

# Configure test database (PostgreSQL required)
export TEST_DATABASE_URL="postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test"

# Run all tests
pytest                                    # All 216 tests
pytest -v                                 # Verbose output
pytest -x                                 # Stop on first failure

# Run with coverage
pytest --cov=app --cov-report=html        # Generate HTML coverage report
pytest --cov=app --cov-report=term        # Show coverage in terminal

# Run specific test files
pytest tests/test_auth.py                 # Authentication tests
pytest tests/test_oauth_service.py        # OAuth service tests
pytest tests/test_jira_collector.py       # Jira collector tests
pytest tests/test_api_security.py         # API security tests
pytest tests/test_calculators.py          # Score calculators
pytest tests/test_normalizers.py          # Metric normalizers

# Run by test class or pattern
pytest tests/test_auth.py::TestTokenValidation  # Specific test class
pytest -k "test_jwt"                            # Tests matching pattern
```

**Note**: Tests automatically create and drop test database tables. Ensure PostgreSQL is running and the test database exists.

### Frontend Tests

```bash
cd frontend

# Run all tests
npm test                                  # Run all 96 tests in watch mode
npm test -- --run                         # Run once without watch
npm test -- --reporter=verbose            # Verbose output

# Run with coverage
npm run test:coverage                     # Generate coverage report

# Run specific test files
npm test -- src/services/__tests__/api.test.ts
npm test -- src/contexts/__tests__/AuthContext.test.tsx
npm test -- src/components/ScoreCard/__tests__/ScoreCard.test.tsx

# Run tests matching pattern
npm test -- -t "ScoreCard"               # Tests with "ScoreCard" in name
```

## Design Principles

1. **Scripts only collect** → calculators decide meaning
2. **All ratios normalized to 0-1** before weighting
3. **Neutral (0.5) only when data genuinely unavailable**
4. **Penalize** when governance tools are disabled
5. **Weights must sum to 1** within each group
6. **Inverted normalization** for "lower is better" metrics

## Roadmap

See [docs/TODO.md](docs/TODO.md) for planned features including:
- Alerts system (early warning, threshold alerts, trend detection)
- Predictions and forecasting (score trends, budget forecast, velocity estimates)
- Visualization enhancements (trend charts, comparative views)
- Google OAuth authentication
- Integrations (team health surveys, SonarQube)

## Contributing

### Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code, releases only |
| `dev` | Active development (default branch) |
| `feature/*` | Feature branches → PR to `dev` |

```bash
# Start a new feature
git checkout dev
git pull
git checkout -b feature/my-feature

# After work is done, push and create PR to dev
git push -u origin feature/my-feature
# Create PR targeting 'dev' branch
```

## Documentation

### Testing
- [Testing Guide](docs/TESTING.md) - Comprehensive testing documentation

### Authentication & Security
- [OAuth 2.0 Setup](docs/OAUTH_SETUP.md) - Jira OAuth authentication guide
- [Security Quick Start](docs/SECURITY_QUICK_START.md) - 5-minute security guide
- [Security Implementation](docs/SECURITY_IMPLEMENTATION.md) - Full security implementation
- [Development Auth](docs/DEVELOPMENT_AUTH.md) - Development authentication details
- [Security Migration Guide](docs/SECURITY_MIGRATION_GUIDE.md) - Production deployment guide
- [Security Audit Report](audits/security.md) - Complete security audit (12 vulnerabilities fixed)

### Development
- [CLAUDE.md](CLAUDE.md) - Guidance for Claude Code
- [Migration Plan](docs/MIGRATION_PLAN.md) - Legacy to new system mapping
- [API Documentation](docs/API.md) - REST API reference
- [Legacy Documentation](legacy/README.md) - Original system docs

### Scripts & Utilities
- `backend/scripts/generate_jwt_token.py` - Generate JWT tokens for testing
- `backend/test_jira_oauth.py` - Test Jira OAuth connection and metrics
- `backend/test_jira_basic.py` - Explore Jira project data

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
