#!/bin/bash

# Script para iniciar el backend del worktree con seed de datos

set -e  # Exit on error

WORKTREE_DIR="/Volumes/Work/Dev/project-score-card/.worktrees/config-db-migration"
BACKEND_DIR="$WORKTREE_DIR/backend"

echo "🛑 Deteniendo backend anterior..."
pkill -f "python run_server.py" 2>/dev/null || echo "   (no había backend corriendo)"
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Force kill any process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 2

echo ""
echo "📊 Ejecutando seed de config_parameters..."
cd "$BACKEND_DIR"
python scripts/seed_config_parameters.py

echo ""
echo "🚀 Iniciando backend del worktree..."
echo "   Directorio: $BACKEND_DIR"
echo "   Puerto: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "   Presiona Ctrl+C para detener"
echo ""

cd "$BACKEND_DIR"
python run_server.py
