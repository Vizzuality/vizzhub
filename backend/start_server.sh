#!/bin/bash

# Navigate to backend directory
cd "$(dirname "$0")"

# Set PYTHONPATH to include the backend directory
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Start uvicorn (it will load .env automatically via pydantic-settings)
echo "Starting backend server..."
echo "PYTHONPATH: $PYTHONPATH"
echo "Working directory: $(pwd)"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
