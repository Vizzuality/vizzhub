#!/bin/bash
# Wrapper script to run the VizzHub MCP server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$PROJECT_ROOT/backend:${PYTHONPATH:-}"

# Load DATABASE_URL from backend/.env if not already set
if [[ -z "$DATABASE_URL" && -f "$PROJECT_ROOT/backend/.env" ]]; then
    DB_URL=$(grep '^DATABASE_URL=' "$PROJECT_ROOT/backend/.env" | cut -d= -f2-)
    if [[ -n "$DB_URL" ]]; then
        export DATABASE_URL="$DB_URL"
    fi
fi

cd "$PROJECT_ROOT"
exec python -m mcp_server
