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

# Install local git hooks via prek (Phase 1 — see docs/code-quality-rollout.md)
hooks:
    @command -v prek >/dev/null 2>&1 || { echo 'prek not installed — run `brew install prek`'; exit 1; }
    prek install --install-hooks

# Run security scanners locally (mirrors what the pre-commit hook runs)
security:
    gitleaks detect --no-banner --redact --verbose

# What CI runs locally (lint check + format check + tests)
ci:
    cd backend && uv run ruff check .
    cd backend && uv run ruff format --check .
    cd backend && uv run pytest -n auto
    cd frontend && npm run lint
    cd frontend && npm test -- --run
