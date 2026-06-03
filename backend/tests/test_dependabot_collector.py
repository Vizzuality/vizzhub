"""Tests for Dependabot alerts collector.

This module tests the DependabotCollector which fetches security alerts
from GitHub's Dependabot API, filtering for high/critical severity only.
"""

import pytest
import respx
from httpx import Response

from app.modules.scorecard.services.collectors.dependabot import DependabotCollector

ALERTS_URL = "https://api.github.com/repos/owner/repo/dependabot/alerts"


class TestFetchAlerts:
    """Tests for DependabotCollector.fetch_alerts method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_returns_high_critical_only(self) -> None:
        """Should filter and return only high/critical severity alerts."""
        mock_alerts = [
            {
                "number": 1,
                "security_vulnerability": {"severity": "critical"},
                "state": "open",
            },
            {
                "number": 2,
                "security_vulnerability": {"severity": "high"},
                "state": "open",
            },
            {
                "number": 3,
                "security_vulnerability": {"severity": "low"},
                "state": "open",
            },
            {
                "number": 4,
                "security_vulnerability": {"severity": "medium"},
                "state": "open",
            },
        ]

        respx.get(ALERTS_URL).mock(return_value=Response(200, json=mock_alerts))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert len(alerts) == 2
        assert all(a["security_vulnerability"]["severity"] in ["critical", "high"] for a in alerts)

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_handles_case_insensitive_severity(self) -> None:
        """Should match severity case-insensitively."""
        mock_alerts = [
            {
                "number": 1,
                "security_vulnerability": {"severity": "CRITICAL"},
                "state": "open",
            },
            {
                "number": 2,
                "security_vulnerability": {"severity": "High"},
                "state": "open",
            },
            {
                "number": 3,
                "security_vulnerability": {"severity": "LOW"},
                "state": "open",
            },
        ]

        respx.get(ALERTS_URL).mock(return_value=Response(200, json=mock_alerts))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert len(alerts) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_returns_empty_on_api_error(self) -> None:
        """Should return empty list when API returns non-200 status."""
        respx.get(ALERTS_URL).mock(return_value=Response(403))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert alerts == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_returns_empty_on_404(self) -> None:
        """Should return empty list when Dependabot not enabled (404)."""
        respx.get(ALERTS_URL).mock(return_value=Response(404))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert alerts == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_returns_empty_when_no_alerts(self) -> None:
        """Should return empty list when no alerts exist."""
        respx.get(ALERTS_URL).mock(return_value=Response(200, json=[]))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert alerts == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_handles_missing_severity(self) -> None:
        """Should handle alerts without severity field gracefully."""
        mock_alerts = [
            {"number": 1, "security_vulnerability": {"severity": "critical"}},
            {"number": 2, "security_vulnerability": {}},  # Missing severity
            {"number": 3},  # Missing security_vulnerability
        ]

        respx.get(ALERTS_URL).mock(return_value=Response(200, json=mock_alerts))

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert len(alerts) == 1
        assert alerts[0]["number"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_sends_correct_headers(self) -> None:
        """Should send correct GitHub API headers."""
        route = respx.get(ALERTS_URL).mock(return_value=Response(200, json=[]))

        await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["Accept"] == "application/vnd.github+json"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_alerts_uses_correct_endpoint(self) -> None:
        """Should call the correct Dependabot alerts endpoint."""
        route = respx.get(ALERTS_URL).mock(return_value=Response(200, json=[]))

        await DependabotCollector.fetch_alerts("owner/repo", "test-token")

        assert route.called
        request = route.calls.last.request
        assert str(request.url).startswith(ALERTS_URL)
        assert "state=open" in str(request.url)
        assert "per_page=100" in str(request.url)


class TestExtractAlertInfo:
    """Tests for DependabotCollector.extract_alert_info method."""

    def test_extract_alert_info_full_data(self) -> None:
        """Should extract all fields from a complete alert."""
        alert = {
            "number": 42,
            "security_vulnerability": {
                "severity": "critical",
                "package": {"name": "lodash"},
            },
            "security_advisory": {
                "identifiers": [
                    {"type": "CVE", "value": "CVE-2024-1234"},
                    {"type": "GHSA", "value": "GHSA-xxxx-yyyy-zzzz"},
                ],
            },
        }

        info = DependabotCollector.extract_alert_info(alert)

        assert info["github_alert_id"] == 42
        assert info["package_name"] == "lodash"
        assert info["severity"] == "critical"
        assert info["cve_id"] == "CVE-2024-1234"

    def test_extract_alert_info_no_cve(self) -> None:
        """Should return None for CVE when no CVE identifier exists."""
        alert = {
            "number": 42,
            "security_vulnerability": {
                "severity": "high",
                "package": {"name": "webpack"},
            },
            "security_advisory": {
                "identifiers": [
                    {"type": "GHSA", "value": "GHSA-xxxx-yyyy-zzzz"},
                ],
            },
        }

        info = DependabotCollector.extract_alert_info(alert)

        assert info["github_alert_id"] == 42
        assert info["package_name"] == "webpack"
        assert info["severity"] == "high"
        assert info["cve_id"] is None

    def test_extract_alert_info_missing_fields(self) -> None:
        """Should handle missing optional fields gracefully."""
        alert = {
            "number": 1,
        }

        info = DependabotCollector.extract_alert_info(alert)

        assert info["github_alert_id"] == 1
        assert info["package_name"] is None
        assert info["severity"] is None
        assert info["cve_id"] is None

    def test_extract_alert_info_empty_identifiers(self) -> None:
        """Should handle empty identifiers list."""
        alert = {
            "number": 5,
            "security_vulnerability": {
                "severity": "critical",
                "package": {"name": "axios"},
            },
            "security_advisory": {
                "identifiers": [],
            },
        }

        info = DependabotCollector.extract_alert_info(alert)

        assert info["github_alert_id"] == 5
        assert info["package_name"] == "axios"
        assert info["severity"] == "critical"
        assert info["cve_id"] is None

    def test_extract_alert_info_no_advisory(self) -> None:
        """Should handle missing security_advisory field."""
        alert = {
            "number": 10,
            "security_vulnerability": {
                "severity": "high",
                "package": {"name": "express"},
            },
        }

        info = DependabotCollector.extract_alert_info(alert)

        assert info["github_alert_id"] == 10
        assert info["package_name"] == "express"
        assert info["severity"] == "high"
        assert info["cve_id"] is None


import logging


class TestFetchAlertsInaccessible:
    @pytest.mark.asyncio
    @respx.mock
    async def test_non_200_returns_empty_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        respx.get(ALERTS_URL).mock(return_value=Response(404))

        with caplog.at_level(logging.WARNING):
            result = await DependabotCollector.fetch_alerts("owner/repo", "token")

        assert result == []
        assert any("dependabot_alerts_inaccessible" in str(r.message) for r in caplog.records)
