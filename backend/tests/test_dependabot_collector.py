"""Tests for Dependabot alerts collector.

This module tests the DependabotCollector which fetches security alerts
from GitHub's Dependabot API, filtering for high/critical severity only.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.collectors.dependabot import DependabotCollector


class TestFetchAlerts:
    """Tests for DependabotCollector.fetch_alerts method."""

    @pytest.mark.asyncio
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

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_alerts

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert len(alerts) == 2
            assert all(
                a["security_vulnerability"]["severity"] in ["critical", "high"]
                for a in alerts
            )

    @pytest.mark.asyncio
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

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_alerts

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_fetch_alerts_returns_empty_on_api_error(self) -> None:
        """Should return empty list when API returns non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 403  # Access denied

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert alerts == []

    @pytest.mark.asyncio
    async def test_fetch_alerts_returns_empty_on_404(self) -> None:
        """Should return empty list when Dependabot not enabled (404)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert alerts == []

    @pytest.mark.asyncio
    async def test_fetch_alerts_returns_empty_when_no_alerts(self) -> None:
        """Should return empty list when no alerts exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert alerts == []

    @pytest.mark.asyncio
    async def test_fetch_alerts_handles_missing_severity(self) -> None:
        """Should handle alerts without severity field gracefully."""
        mock_alerts = [
            {"number": 1, "security_vulnerability": {"severity": "critical"}},
            {"number": 2, "security_vulnerability": {}},  # Missing severity
            {"number": 3},  # Missing security_vulnerability
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_alerts

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            alerts = await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            assert len(alerts) == 1
            assert alerts[0]["number"] == 1

    @pytest.mark.asyncio
    async def test_fetch_alerts_sends_correct_headers(self) -> None:
        """Should send correct GitHub API headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            headers = call_args.kwargs.get("headers", {})

            assert headers["Authorization"] == "Bearer test-token"
            assert headers["Accept"] == "application/vnd.github+json"
            assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    @pytest.mark.asyncio
    async def test_fetch_alerts_uses_correct_endpoint(self) -> None:
        """Should call the correct Dependabot alerts endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            await DependabotCollector.fetch_alerts("owner/repo", "test-token")

            call_args = mock_get.call_args
            url = call_args.args[0]
            params = call_args.kwargs.get("params", {})

            assert url == "https://api.github.com/repos/owner/repo/dependabot/alerts"
            assert params["state"] == "open"
            assert params["per_page"] == 100


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
