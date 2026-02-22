"""Tests for ISO Google Workspace OAuth."""

import pytest
from app.config import get_settings


class TestGoogleWorkspaceConfig:
    def test_config_has_google_workspace_fields(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert hasattr(settings, "google_workspace_client_id")
        assert hasattr(settings, "google_workspace_client_secret")
        assert hasattr(settings, "google_workspace_redirect_uri")
        assert settings.google_workspace_client_id == ""
        assert settings.google_workspace_client_secret == ""
        assert settings.google_workspace_redirect_uri == ""
