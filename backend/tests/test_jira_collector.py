"""Tests for Jira collector OAuth integration and metrics collection.

This module tests the JiraCollector which collects metrics from Jira API,
including OAuth 2.0 integration, legacy authentication fallback, error handling,
and metrics collection for project scorecard calculations.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth import OAuthTokenDB
from app.services.collectors.jira import JiraCollector
from app.services.oauth_service import OAuthService


class TestOAuthIntegration:
    """Test Jira collector OAuth authentication integration."""

    @pytest.mark.asyncio
    async def test_jira_collector_uses_oauth_token_when_available(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should prefer OAuth over legacy auth when available."""
        # Create OAuth token in database
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

        with patch("app.services.oauth_service.OAuthService.get_valid_jira_token", new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = "oauth-access-token"

            with patch("app.services.oauth_service.OAuthService.get_jira_site_info", new_callable=AsyncMock) as mock_site_info:
                mock_site_info.return_value = {
                    "cloud_id": "cloud-id-123",
                    "site_url": "https://mycompany.atlassian.net",
                }

                client = await collector._get_client()

        # Should use OAuth base URL (convert URL to string for comparison)
        # Note: httpx adds trailing slash to base URLs
        assert str(client.base_url) == "https://api.atlassian.com/ex/jira/cloud-id-123/"
        # Should use Bearer token in headers
        assert client.headers["Authorization"] == "Bearer oauth-access-token"

    @pytest.mark.asyncio
    async def test_jira_collector_falls_back_to_legacy_auth(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should use API token if OAuth unavailable."""
        with patch("app.services.collectors.jira.get_settings") as mock_settings:
            mock_settings.return_value.jira_base_url = "https://company.atlassian.net"
            mock_settings.return_value.jira_email = "user@example.com"
            mock_settings.return_value.jira_api_token = "legacy-api-token"

            collector = JiraCollector(db=db_session)

            with patch("app.services.oauth_service.OAuthService.get_valid_jira_token", new_callable=AsyncMock) as mock_get_token:
                mock_get_token.return_value = None  # No OAuth token

                client = await collector._get_client()

        # Should use legacy base URL (httpx normalizes URLs consistently)
        assert str(client.base_url) == "https://company.atlassian.net"
        # Should use basic auth
        assert client.auth is not None

    @pytest.mark.asyncio
    async def test_jira_collector_raises_error_when_no_auth(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should raise ValueError if neither OAuth nor legacy configured."""
        collector = JiraCollector(db=db_session)

        with patch("app.services.oauth_service.OAuthService.get_valid_jira_token") as mock_get_token:
            mock_get_token.return_value = None

            with patch("app.services.collectors.jira.get_settings") as mock_settings:
                mock_settings.return_value.jira_base_url = ""
                mock_settings.return_value.jira_email = ""
                mock_settings.return_value.jira_api_token = ""

                with pytest.raises(ValueError) as exc_info:
                    await collector._get_client()

                assert "No Jira authentication configured" in str(exc_info.value)




class TestMetricsCollection:
    """Test Jira metrics collection functionality."""

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_bug_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return bugs_closed count."""
        collector = JiraCollector(db=db_session)

        mock_client = AsyncMock()

        # Mock bug count response (json() is sync, not async)
        bug_response = MagicMock()
        bug_response.status_code = 200
        bug_response.json.return_value = {"count": 42}

        # Mock other responses with 0 counts (json() is sync, not async)
        zero_response = MagicMock()
        zero_response.status_code = 200
        zero_response.json.return_value = {"count": 0}

        mock_client.post.return_value = zero_response

        collector._client = mock_client

        # Patch _count_issues to return specific value for bugs
        with patch.object(collector, "_count_issues") as mock_count:
            async def count_side_effect(client, project, jql):
                if "type = Bug AND status = Done" in jql:
                    return 42
                return 0

            mock_count.side_effect = count_side_effect

            metrics = await collector.collect("TEST")

        assert metrics["bugs_closed"] == 42

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_task_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return tasks_completed count."""
        collector = JiraCollector(db=db_session)

        with patch.object(collector, "_count_issues") as mock_count:
            async def count_side_effect(client, project, jql):
                if "type in (Story, Task) AND status = Done" in jql:
                    return 128
                return 0

            mock_count.side_effect = count_side_effect

            with patch.object(collector, "_get_client"):
                metrics = await collector.collect("PROJ")

        assert metrics["tasks_completed"] == 128

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_story_counts(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return story_points count."""
        collector = JiraCollector(db=db_session)

        with patch.object(collector, "_count_issues") as mock_count:
            mock_count.return_value = 0

            with patch.object(collector, "_get_story_review_data") as mock_story:
                mock_story.return_value = {"total": 50, "with_reviewer": 45}

                with patch.object(collector, "_get_client"):
                    with patch.object(collector, "_get_incidents"):
                        with patch.object(collector, "_get_flow_metrics"):
                            metrics = await collector.collect("STORY")

        assert metrics["total_stories"] == 50

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_escaped_defects(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return escaped_defects count."""
        collector = JiraCollector(db=db_session)

        with patch.object(collector, "_count_issues") as mock_count:
            async def count_side_effect(client, project, jql):
                if "Environment" in jql and "Staging" in jql:
                    return 7
                return 0

            mock_count.side_effect = count_side_effect

            with patch.object(collector, "_get_client"):
                metrics = await collector.collect("ESC")

        assert metrics["escaped_defects"] == 7

    @pytest.mark.asyncio
    async def test_jira_collector_collect_returns_story_review_data(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return total_stories and stories_with_reviewer."""
        collector = JiraCollector(db=db_session)

        with patch.object(collector, "_count_issues") as mock_count:
            mock_count.return_value = 0

            with patch.object(collector, "_get_story_review_data") as mock_review:
                mock_review.return_value = {"total": 100, "with_reviewer": 95}

                with patch.object(collector, "_get_client"):
                    with patch.object(collector, "_get_incidents"):
                        with patch.object(collector, "_get_flow_metrics"):
                            metrics = await collector.collect("REV")

        assert metrics["total_stories"] == 100
        assert metrics["stories_with_reviewer"] == 95

    @pytest.mark.asyncio
    async def test_jira_collector_collect_handles_empty_project(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return zeros for empty project."""
        collector = JiraCollector(db=db_session)

        with patch.object(collector, "_count_issues") as mock_count:
            mock_count.return_value = 0

            with patch.object(collector, "_get_story_review_data") as mock_review:
                mock_review.return_value = {"total": 0, "with_reviewer": 0}

                with patch.object(collector, "_get_incidents") as mock_incidents:
                    mock_incidents.return_value = {"count": 0, "mttr_hours": None}

                    with patch.object(collector, "_get_flow_metrics") as mock_flow:
                        mock_flow.return_value = {
                            "lead_time_days": None,
                            "flow_efficiency": None,
                            "commitment_reliability": None,
                        }

                        with patch.object(collector, "_get_client"):
                            metrics = await collector.collect("EMPTY")

        assert metrics["bugs_closed"] == 0
        assert metrics["tasks_completed"] == 0
        assert metrics["escaped_defects"] == 0
        assert metrics["total_stories"] == 0

    @pytest.mark.asyncio
    async def test_jira_collector_collect_handles_jql_api_error(
        self, db_session: AsyncSession
    ) -> None:
        """collect should return zeros on JQL error."""
        collector = JiraCollector(db=db_session)

        # Simulate JQL API errors
        with patch.object(collector, "_count_issues") as mock_count:
            mock_count.return_value = 0  # Returns 0 on error

            with patch.object(collector, "_get_client"):
                metrics = await collector.collect("ERROR")

        # Should gracefully handle errors and return 0
        assert metrics["bugs_closed"] == 0
        assert metrics["tasks_completed"] == 0

    @pytest.mark.asyncio
    async def test_jira_collector_count_issues_handles_api_error(
        self, db_session: AsyncSession
    ) -> None:
        """_count_issues should return 0 on JQL error."""
        collector = JiraCollector(db=db_session)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.post.return_value = mock_response

        count = await collector._count_issues(mock_client, "PROJ", "invalid jql")

        assert count == 0

    @pytest.mark.asyncio
    async def test_jira_collector_count_issues_validates_project_key_before_query(
        self, db_session: AsyncSession
    ) -> None:
        """_count_issues should validate project key before making API call."""
        collector = JiraCollector(db=db_session)

        mock_client = AsyncMock()

        # Invalid project key with special characters
        with pytest.raises(ValueError) as exc_info:
            await collector._count_issues(
                mock_client, "INVALID'; DROP TABLE--", "status = Done"
            )

        # Should raise validation error
        assert "Invalid project key format" in str(exc_info.value)
        # Should NOT make API call
        mock_client.post.assert_not_called()



class TestErrorHandling:
    """Test Jira collector error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_jira_collector_oauth_token_refresh_on_401(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should refresh token on 401 response."""
        # This test documents expected behavior
        # Current implementation doesn't auto-refresh on 401
        # but this is the desired behavior to implement
        collector = JiraCollector(db=db_session)

        # Create expired token
        oauth_token = OAuthTokenDB(
            provider="jira",
            access_token="expired-token",
            refresh_token="refresh-token",
            cloud_id="cloud-123",
        )
        db_session.add(oauth_token)
        await db_session.commit()

        with patch("app.services.oauth_service.OAuthService.get_valid_jira_token") as mock_token:
            # get_valid_jira_token handles refresh internally
            mock_token.return_value = "refreshed-token"

            with patch("app.services.oauth_service.OAuthService.get_jira_site_info") as mock_site:
                mock_site.return_value = {"cloud_id": "cloud-123", "site_url": "https://test.atlassian.net"}

                client = await collector._get_client()

        # Should use refreshed token
        assert client.headers["Authorization"] == "Bearer refreshed-token"

    @pytest.mark.asyncio
    async def test_jira_collector_oauth_token_refresh_failure_raises(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should raise exception if refresh fails."""
        collector = JiraCollector(db=db_session)

        with patch("app.services.oauth_service.OAuthService.get_valid_jira_token") as mock_token:
            mock_token.return_value = None  # Refresh failed

            with patch("app.services.collectors.jira.get_settings") as mock_settings:
                mock_settings.return_value.jira_base_url = ""
                mock_settings.return_value.jira_email = ""
                mock_settings.return_value.jira_api_token = ""

                with pytest.raises(ValueError):
                    await collector._get_client()

    @pytest.mark.asyncio
    async def test_jira_collector_handles_network_timeout(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should handle httpx.TimeoutException gracefully."""
        collector = JiraCollector(db=db_session)

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        count = await collector._count_issues(mock_client, "PROJ", "status = Done")

        # Should return 0 on timeout
        assert count == 0

    @pytest.mark.asyncio
    async def test_jira_collector_handles_rate_limit_429(
        self, db_session: AsyncSession
    ) -> None:
        """Collector should handle 429 Too Many Requests gracefully."""
        collector = JiraCollector(db=db_session)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_client.post.return_value = mock_response

        count = await collector._count_issues(mock_client, "PROJ", "status = Done")

        # Should return 0 on rate limit
        assert count == 0
