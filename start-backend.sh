#!/bin/bash


set -e  # Exit on error

WORKTREE_DIR="/Volumes/Work/Dev/project-score-card/.worktrees/config-db-migration"
BACKEND_DIR="$WORKTREE_DIR/backend"

echo " stoping..."
pkill -f "python run_server.py" 2>/dev/null || echo "   (no backend running)"
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Force kill any process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 2

echo ""
echo " Running seeds..."
cd "$BACKEND_DIR"
python scripts/seed_config_parameters.py "$@"

echo ""
echo "   Starting..."
echo "   Dir: $BACKEND_DIR"
echo "   Port: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

cd "$BACKEND_DIR"
python run_server.py
