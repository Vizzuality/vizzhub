"""Tests for `core/services/jira_client.JiraClient`.

These tests focus on the pure validation surface and the connection-test
fallback paths. Network round-trips are mocked via `respx`.
"""

import pytest

from app.core.exceptions import ConfigurationError
from app.core.services.jira_client import JiraClient


class TestValidateProjectKey:
    def test_accepts_letters_numbers_hyphens_underscores(self) -> None:
        client = JiraClient(db=None)
        # All of these must not raise.
        client.validate_project_key("ABC")
        client.validate_project_key("ABC123")
        client.validate_project_key("my-key")
        client.validate_project_key("my_key")

    def test_rejects_empty(self) -> None:
        client = JiraClient(db=None)
        with pytest.raises(ValueError, match="Invalid project key"):
            client.validate_project_key("")

    def test_rejects_special_chars_jql_injection(self) -> None:
        """The validator's purpose is to block JQL injection — spaces, quotes, semicolons must fail."""
        client = JiraClient(db=None)
        bad_keys = [
            'PROJ" OR 1=1 --',
            "PROJ; DROP TABLE",
            "PROJ AND foo",
            "PROJ'",
            "PROJ*",
        ]
        for key in bad_keys:
            with pytest.raises(ValueError, match="Invalid project key"):
                client.validate_project_key(key)

    def test_rejects_too_long(self) -> None:
        client = JiraClient(db=None)
        with pytest.raises(ValueError, match="Invalid project key"):
            client.validate_project_key("A" * 21)


@pytest.mark.asyncio
async def test_get_client_raises_when_no_auth_configured(monkeypatch) -> None:
    """If neither OAuth nor legacy creds are present, _get_client raises ConfigurationError."""
    client = JiraClient(db=None)
    monkeypatch.setattr(client.settings, "jira_base_url", "")
    monkeypatch.setattr(client.settings, "jira_oauth_client_id", "")

    with pytest.raises(ConfigurationError, match="No Jira authentication"):
        await client._get_client()


@pytest.mark.asyncio
async def test_get_client_raises_oauth_unauthorized(monkeypatch) -> None:
    """If OAuth is configured but no token, the error message points the user at /authorize."""
    client = JiraClient(db=None)
    monkeypatch.setattr(client.settings, "jira_base_url", "")
    monkeypatch.setattr(client.settings, "jira_oauth_client_id", "fake-client-id")

    with pytest.raises(ConfigurationError, match="OAuth is configured but not authorized"):
        await client._get_client()


@pytest.mark.asyncio
async def test_test_connection_returns_false_on_non_200(monkeypatch) -> None:
    """A 401/404/500 must surface as False, not raise."""
    import httpx

    class _FakeClient:
        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(401)

        async def aclose(self) -> None:
            return None

    client = JiraClient(db=None)
    client._client = _FakeClient()  # type: ignore[assignment]

    result = await client.test_connection()
    assert result is False


@pytest.mark.asyncio
async def test_test_connection_returns_false_on_http_error() -> None:
    """A network error (httpx.HTTPError) is swallowed and returns False."""
    import httpx

    class _RaisingClient:
        async def get(self, url: str) -> httpx.Response:
            raise httpx.ConnectError("network down")

        async def aclose(self) -> None:
            return None

    client = JiraClient(db=None)
    client._client = _RaisingClient()  # type: ignore[assignment]

    result = await client.test_connection()
    assert result is False


@pytest.mark.asyncio
async def test_count_issues_validates_project_key() -> None:
    """count_issues runs the validator before any network call."""
    client = JiraClient(db=None)
    with pytest.raises(ValueError):
        await client.count_issues("BAD KEY WITH SPACES", "type = Bug")


@pytest.mark.asyncio
async def test_search_issues_validates_project_key() -> None:
    client = JiraClient(db=None)
    with pytest.raises(ValueError):
        await client.search_issues("'OR 1=1", "type = Bug")
