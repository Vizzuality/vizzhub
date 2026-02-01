#!/bin/bash
# Wrapper script to load .env.local and run SonarQube MCP server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env.local
if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)
fi

# Map SONARCLOUD_TOKEN to SONARQUBE_TOKEN (MCP expects SONARQUBE_TOKEN)
if [[ -n "$SONARCLOUD_TOKEN" ]]; then
    export SONARQUBE_TOKEN="$SONARCLOUD_TOKEN"
fi

# Run the MCP server
exec npx -y sonarqube-mcp-server@latest
