"""Integration admin API schemas."""

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    """Status of an individual integration provider."""

    connected: bool
    expires_at: str | None = None
    token_type: str | None = None
    site_url: str | None = None
    created_at: str | None = None


class AllIntegrationsStatus(BaseModel):
    """Status of all integration providers."""

    jira: ProviderStatus
    google_workspace: ProviderStatus
    github: ProviderStatus
    slack: ProviderStatus
    slack_settings: dict[str, str | None] = {}


class GitHubTokenInput(BaseModel):
    """Input for saving a GitHub Personal Access Token."""

    token: str = Field(..., min_length=1, description="GitHub Personal Access Token")


class SlackTokenInput(BaseModel):
    """Input for saving a Slack bot token."""

    token: str = Field(..., min_length=1, description="Slack bot token (xoxb-...)")


class SlackSettingsUpdate(BaseModel):
    """Update Slack integration settings."""

    leadership_channel_id: str | None = Field(None, max_length=50)
