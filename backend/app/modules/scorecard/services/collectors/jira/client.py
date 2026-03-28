"""Re-export JiraClient from core for backward compatibility."""

from app.core.services.jira_client import JiraClient

__all__ = ["JiraClient"]
