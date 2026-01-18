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

# Frontend
cd frontend
npm run dev                                   # Start development server

# Generate JWT tokens (for testing authenticated endpoints)
cd backend
python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
```

### Docker (Alternative)

```bash
# Start all services (PostgreSQL, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart after changes
docker-compose down && docker-compose up -d --build
```

### Backend (FastAPI)

```bash
cd backend

# Run tests
pytest                                        # All tests (270 total)
pytest tests/test_calculators.py              # Single file
pytest tests/test_normalizers.py::TestLowerIsBetter  # Single class
pytest -k "test_perfect_score"                # By name pattern

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
npm test         # Run tests
```

## Architecture

### Backend Data Flow

```
Raw Metrics → Normalizers → Indicators (0-1) → Calculators → Scores (0-100)
```

1. **Collectors** (`services/collectors/`): Fetch data from Jira/GitHub APIs. Collectors only collect—they do not interpret.

2. **Normalizers** (`services/normalizers/`): Transform raw metrics to 0-1 scale using these patterns:
   - Higher is better: `min(1, value)`
   - Lower is better: `min(1, target / max(value, 0.001))`
   - Missing data: return 0.5 (neutral)
   - Strict zero target: if target=0 and value>0, return 0

3. **Calculators** (`services/calculators/`): Apply weights from `scoring_config.yaml` to produce 0-100 scores. Each dimension has its own calculator class.

4. **FinalScoreCalculator**: Aggregates all 8 dimension scores using global weights.

### Configuration

All weights and targets are in `backend/scoring_config.yaml`. Weight groups must sum to 1.0. The `ScoringConfig` class loads this and provides `validate_weights()`.

### Key Design Rules

- Scores are computed on-the-fly, not stored (ensures config changes apply immediately)
- Sev1 incidents cap P_quality at 60 points
- Milestones have a grace period (default 3 days)
- Disabled governance tools get penalized (score = 0), not neutral

### Database

PostgreSQL with async SQLAlchemy. Tables: `projects`, `metrics`, `oauth_tokens`. Indicators and scores are computed, not persisted.

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
├── api/              # API endpoints (projects, metrics, oauth, collectors, config)
├── core/             # Core security modules (auth, oauth_state, security_logger, middleware)
├── models/           # SQLAlchemy models (Project, Metrics, Indicators, Scores, OAuthToken)
├── services/
│   ├── calculators/  # Score calculators for 8 dimensions
│   ├── collectors/   # Data collectors (Jira, GitHub)
│   └── normalizers/  # Metric normalization (raw → 0-1 scale)
├── config.py         # Settings (Pydantic)
├── database.py       # Database connection
└── main.py           # FastAPI app

scripts/              # Utility scripts (generate_jwt_token.py)
tests/                # Pytest tests
```

### Frontend (`frontend/src/`)
```
components/           # React components (Dashboard, ProjectCard, etc.)
contexts/             # React contexts (AuthContext)
hooks/                # Custom hooks (useAuth, useProjects, useMetrics, useCollectors)
pages/                # Page components (ProjectDetail, Login)
services/             # API clients (api.ts with JWT interceptors)
types/                # TypeScript types (auth.ts, index.ts)
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
