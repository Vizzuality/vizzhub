#!/bin/bash
cd /Volumes/Work/Dev/project-score-card/backend
export PYTHONPATH=/Volumes/Work/Dev/project-score-card/backend
export $(cat .env | grep -v '^#' | xargs)
python test_jira_oauth.py "$@"
