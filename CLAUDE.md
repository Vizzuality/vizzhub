# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Project Scorecard evaluates software development projects across 8 dimensions (P_time, P_cost, P_quality, P_value, P_satisfaction, P_flow, P_engineering, P_risk). Migrated from Google Sheets to FastAPI + React.

## Commands

### Development

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
pytest
pytest tests/test_calculators.py              # Single file
pytest tests/test_normalizers.py::TestLowerIsBetter  # Single class
pytest -k "test_perfect_score"                # By name pattern

# Run with coverage
pytest --cov=app

# Linting
ruff check app/
black app/

# Run server manually (if not using Docker)
uvicorn app.main:app --reload
```

### Frontend (React)

```bash
cd frontend
npm run dev      # Development server
npm run build    # Production build
npm run lint     # ESLint
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

PostgreSQL with async SQLAlchemy. Tables: `projects`, `metrics`. Indicators and scores are computed, not persisted.

## Coding Standards

### Python
- Type hints required on all functions
- Use `X | None` not `Optional[X]`
- Use `list[str]` not `List[str]`
- Formatter: Black (88 chars), Linter: Ruff

### TypeScript
- Strict mode, explicit return types
- Prefer `interface` over `type` for objects
- No `any`—use `unknown` if needed
