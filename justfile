# Show available recipes (default when running `just` with no args)
default:
    @just --list

# Run all linters (read-only)
lint:
    cd backend && uv run ruff check .
    cd frontend && npm run lint

# Auto-fix lint issues and format code
format:
    cd backend && uv run ruff check --fix .
    cd backend && uv run ruff format .

# Run security scanners (added in later rollout phases — see docs/code-quality-rollout.md)
security:
    @echo "Security scanners come online in later phases:"
    @echo "  Phase 1: gitleaks (pre-commit + nightly)"
    @echo "  Phase 3: semgrep (PR gate)"
    @echo "  Phase 5: trivy, pip-audit, npm audit (nightly)"
    @echo "Nothing to run yet at Phase 0."

# What CI runs locally (lint check + format check + tests)
ci:
    cd backend && uv run ruff check .
    cd backend && uv run ruff format --check .
    cd backend && uv run pytest -n auto
    cd frontend && npm run lint
    cd frontend && npm test -- --run
