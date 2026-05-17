"""Tests for GitHub Vulnerabilities collector."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scorecard.services.collectors.github.vulnerabilities import (
    _get_dependabot_alerts,
    collect_vulnerabilities,
)


def make_alert(days_ago: int, severity: str = "high") -> dict:
    """Helper to create a Dependabot alert dict."""
    created = datetime.now(UTC) - timedelta(days=days_ago)
    return {
        "number": days_ago,
        "created_at": created.isoformat(),
        "state": "open",
        "security_advisory": {"severity": severity},
        "dependency": {"package": {"name": f"pkg-{days_ago}"}},
    }


class TestCollectVulnerabilities:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_alerts(self, mock_github_client) -> None:
        """Should return 0 when no alerts exist."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        assert result["high_severity_vulns"] == 0
        assert result["high_severity_vulns_total"] == 0

    @pytest.mark.asyncio
    async def test_counts_alerts_older_than_30_days(self, mock_github_client) -> None:
        """Should count alerts older than 30 days."""
        mock_http = AsyncMock()
        alerts = [
            make_alert(10),  # 10 days old - NOT counted
            make_alert(20),  # 20 days old - NOT counted
            make_alert(40),  # 40 days old - counted
            make_alert(60),  # 60 days old - counted
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: alerts)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        assert result["high_severity_vulns"] == 2  # Only >30 days
        assert result["high_severity_vulns_total"] == 4  # All alerts

    @pytest.mark.asyncio
    async def test_returns_zero_when_dependabot_not_enabled(self, mock_github_client) -> None:
        """Should return 0 when Dependabot not enabled (403)."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=403)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        assert result["high_severity_vulns"] == 0
        assert result["high_severity_vulns_total"] == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_repo_not_found(self, mock_github_client) -> None:
        """Should return 0 when repository not found (404)."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=404)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        assert result["high_severity_vulns"] == 0
        assert result["high_severity_vulns_total"] == 0

    @pytest.mark.asyncio
    async def test_handles_boundary_29_days(self, mock_github_client) -> None:
        """Should handle boundary case of 29 days old alert (not counted)."""
        mock_http = AsyncMock()
        alerts = [make_alert(29)]  # 29 days old - should NOT be counted (< 30 days)
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: alerts)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        # 29 days is < 30, so should not be counted
        assert result["high_severity_vulns"] == 0
        assert result["high_severity_vulns_total"] == 1

    @pytest.mark.asyncio
    async def test_handles_31_days(self, mock_github_client) -> None:
        """Alert at 31 days should be counted."""
        mock_http = AsyncMock()
        alerts = [make_alert(31)]  # 31 days old - counted
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: alerts)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_vulnerabilities(mock_github_client, "owner/repo")

        assert result["high_severity_vulns"] == 1


class TestGetDependabotAlerts:
    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self, mock_github_client) -> None:
        """Should return None on API error."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=500)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await _get_dependabot_alerts(mock_github_client, "owner", "repo")

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, mock_github_client) -> None:
        """Should handle empty alert list."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await _get_dependabot_alerts(mock_github_client, "owner", "repo")

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_by_severity(self, mock_github_client) -> None:
        """API call should filter by high,critical severity."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        await _get_dependabot_alerts(mock_github_client, "owner", "repo")

        # Verify the API was called with correct severity filter
        call_args = mock_http.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("severity") == "high,critical"
        assert params.get("state") == "open"
