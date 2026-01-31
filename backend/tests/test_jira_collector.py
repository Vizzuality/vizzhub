"""Tests for Jira collector OAuth integration and metrics collection.

This module tests the JiraCollector which collects metrics from Jira API,
including OAuth 2.0 integration, legacy authentication fallback, error handling,
and metrics collection for project scorecard calculations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConfigurationError
from app.models.oauth import OAuthTokenDB
from app.services.collectors.jira import JiraCollector
from app.services.collectors.jira.client import JiraClient


class TestOAuthIntegration:
    """Test Jira collector OAuth authentication integration."""

    @pytest.mark.asyncio
    async def test_jira_collector_uses_oauth_token_when_available(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should prefer OAuth over legacy auth when available."""
        oauth_token = OAuthTokenDB(
            provider="jira",
            access_token="oauth-access-token",
            refresh_token="oauth-refresh-token",
            cloud_id="cloud-id-123",
            site_url="https://mycompany.atlassian.net",
        )
        db_session.add(oauth_token)
        await db_session.commit()

        collector = JiraCollector(db=db_session)

        with patch(
            "app.services.collectors.jira.client.OAuthService.get_valid_jira_token",
            new_callable=AsyncMock,
        ) as mock_get_token:
            mock_get_token.return_value = "oauth-access-token"

            with patch(
                "app.services.collectors.jira.client.OAuthService.get_jira_site_info",
                new_callable=AsyncMock,
            ) as mock_site_info:
                mock_site_info.return_value = {
                    "cloud_id": "cloud-id-123",
                    "site_url": "https://mycompany.atlassian.net",
                }

                client = await collector._jira_client._get_client()

        assert str(client.base_url) == "https://api.atlassian.com/ex/jira/cloud-id-123/"
        assert client.headers["Authorization"] == "Bearer oauth-access-token"

    @pytest.mark.asyncio
    async def test_jira_collector_falls_back_to_legacy_auth(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should use API token if OAuth unavailable."""
        with patch("app.services.collectors.jira.client.get_settings") as mock_settings:
            mock_settings.return_value.jira_base_url = "https://company.atlassian.net"
            mock_settings.return_value.jira_email = "user@example.com"
            mock_settings.return_value.jira_api_token = "legacy-api-token"

            collector = JiraCollector(db=db_session)

            with patch(
                "app.services.collectors.jira.client.OAuthService.get_valid_jira_token",
                new_callable=AsyncMock,
            ) as mock_get_token:
                mock_get_token.return_value = None

                client = await collector._jira_client._get_client()

        assert str(client.base_url) == "https://company.atlassian.net"
        assert client.auth is not None

    @pytest.mark.asyncio
    async def test_jira_collector_raises_error_when_no_auth(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should raise ConfigurationError if neither OAuth nor legacy configured."""
        with patch(
            "app.services.collectors.jira.client.OAuthService.get_valid_jira_token"
        ) as mock_get_token:
            mock_get_token.return_value = None

            with patch(
                "app.services.collectors.jira.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value.jira_base_url = ""
                mock_settings.return_value.jira_email = ""
                mock_settings.return_value.jira_api_token = ""
                mock_settings.return_value.jira_oauth_client_id = ""

                # Create collector inside patches so settings are mocked
                collector = JiraCollector(db=db_session)

                with pytest.raises(ConfigurationError) as exc_info:
                    await collector._jira_client._get_client()

                assert "No Jira authentication configured" in str(exc_info.value)


class TestMetricsCollection:
    """Test Jira metrics collection functionality."""

    def _mock_jira_client(self, collector: JiraCollector) -> None:
        """Set up common mocks for JiraClient methods."""
        collector._jira_client.count_issues = AsyncMock(return_value=0)
        collector._jira_client.search_issues = AsyncMock(return_value=[])
        collector._jira_client.get_client = AsyncMock()

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_bug_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return bugs_total count."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        async def count_side_effect(project, jql):
            if jql == "type = Bug":
                return 42
            return 0

        collector._jira_client.count_issues.side_effect = count_side_effect

        metrics = await collector.collect("TEST")

        assert metrics.bugs_total == 42

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_task_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return tasks_completed count."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        async def count_side_effect(project, jql):
            if "type in (Story, Task, Sub-task) AND statusCategory = Done" in jql:
                return 128
            return 0

        collector._jira_client.count_issues.side_effect = count_side_effect

        metrics = await collector.collect("PROJ")

        assert metrics.tasks_completed == 128

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_story_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return story counts."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        async def count_side_effect(project, jql):
            if jql == "type = Story AND status = Done":
                return 50
            if "reviewers IS NOT EMPTY" in jql:
                return 45
            return 0

        collector._jira_client.count_issues.side_effect = count_side_effect

        metrics = await collector.collect("STORY")

        assert metrics.total_stories == 50
        assert metrics.stories_with_reviewer == 45

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_escaped_defects(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return escaped_defects count."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        async def count_side_effect(project, jql):
            if "Environment" in jql and "Staging" in jql:
                return 7
            return 0

        collector._jira_client.count_issues.side_effect = count_side_effect

        metrics = await collector.collect("ESC")

        assert metrics.escaped_defects == 7

    @pytest.mark.asyncio
    async def test_jira_collector_collect_handles_empty_project(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return zeros/None for empty project."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        metrics = await collector.collect("EMPTY")

        assert metrics.bugs_total == 0
        assert metrics.tasks_completed == 0
        assert metrics.escaped_defects == 0
        assert metrics.total_stories == 0

    @pytest.mark.asyncio
    async def test_jira_collector_collect_handles_jql_api_error(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return zeros on JQL error."""
        collector = JiraCollector(db=db_session)
        self._mock_jira_client(collector)

        metrics = await collector.collect("ERROR")

        assert metrics.bugs_total == 0
        assert metrics.tasks_completed == 0


class TestJiraClientCountIssues:
    """Test JiraClient.count_issues method."""

    @pytest.mark.asyncio
    async def test_count_issues_handles_api_error(
        self, db_session: AsyncSession
    ) -> None:
        """count_issues should return 0 on JQL error."""
        jira_client = JiraClient(db=db_session)

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_http_client.post.return_value = mock_response

        jira_client._client = mock_http_client

        count = await jira_client.count_issues("PROJ", "invalid jql")

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_issues_validates_project_key_before_query(
        self, db_session: AsyncSession
    ) -> None:
        """count_issues should validate project key before making API call."""
        jira_client = JiraClient(db=db_session)

        mock_http_client = AsyncMock()
        jira_client._client = mock_http_client

        with pytest.raises(ValueError) as exc_info:
            await jira_client.count_issues("INVALID'; DROP TABLE--", "status = Done")

        assert "Invalid project key format" in str(exc_info.value)
        mock_http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_issues_handles_network_timeout(
        self, db_session: AsyncSession
    ) -> None:
        """count_issues should handle httpx.TimeoutException gracefully."""
        jira_client = JiraClient(db=db_session)

        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = httpx.TimeoutException("Request timeout")
        jira_client._client = mock_http_client

        count = await jira_client.count_issues("PROJ", "status = Done")

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_issues_handles_rate_limit_429(
        self, db_session: AsyncSession
    ) -> None:
        """count_issues should handle 429 Too Many Requests gracefully."""
        jira_client = JiraClient(db=db_session)

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_http_client.post.return_value = mock_response
        jira_client._client = mock_http_client

        count = await jira_client.count_issues("PROJ", "status = Done")

        assert count == 0


class TestErrorHandling:
    """Test Jira collector error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_jira_collector_oauth_token_refresh_on_401(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should refresh token on 401 response."""
        oauth_token = OAuthTokenDB(
            provider="jira",
            access_token="expired-token",
            refresh_token="refresh-token",
            cloud_id="cloud-123",
        )
        db_session.add(oauth_token)
        await db_session.commit()

        collector = JiraCollector(db=db_session)

        with patch(
            "app.services.collectors.jira.client.OAuthService.get_valid_jira_token"
        ) as mock_token:
            mock_token.return_value = "refreshed-token"

            with patch(
                "app.services.collectors.jira.client.OAuthService.get_jira_site_info"
            ) as mock_site:
                mock_site.return_value = {
                    "cloud_id": "cloud-123",
                    "site_url": "https://test.atlassian.net",
                }

                client = await collector._jira_client._get_client()

        assert client.headers["Authorization"] == "Bearer refreshed-token"

    @pytest.mark.asyncio
    async def test_jira_collector_oauth_token_refresh_failure_raises(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should raise exception if refresh fails."""
        collector = JiraCollector(db=db_session)

        with patch(
            "app.services.collectors.jira.client.OAuthService.get_valid_jira_token"
        ) as mock_token:
            mock_token.return_value = None

            with patch(
                "app.services.collectors.jira.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value.jira_base_url = ""
                mock_settings.return_value.jira_email = ""
                mock_settings.return_value.jira_api_token = ""
                mock_settings.return_value.jira_oauth_client_id = ""

                with pytest.raises(ConfigurationError):
                    await collector._jira_client._get_client()
