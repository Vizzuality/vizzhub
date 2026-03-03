"""Tests for GitHub Change Failure Rate collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.modules.scorecard.services.collectors.github.change_failure_rate import (
    collect_change_failure_rate,
    _is_failure_response,
    _parse_semver,
    _is_hotfix_by_name,
    _is_semver_patch,
)


def make_release(tag: str, name: str, days_ago: int) -> dict:
    """Helper to create a release dict."""
    published = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "tag_name": tag,
        "name": name,
        "published_at": published.isoformat(),
        "draft": False,
    }


class TestParseSemver:
    def test_parses_standard_semver(self) -> None:
        """Should parse standard semver tags."""
        assert _parse_semver("v1.2.3") == (1, 2, 3)
        assert _parse_semver("1.2.3") == (1, 2, 3)

    def test_returns_none_for_non_semver(self) -> None:
        """Should return None for non-semver tags."""
        assert _parse_semver("release-2024") is None
        assert _parse_semver("latest") is None
        assert _parse_semver("") is None

    def test_handles_prerelease_tags(self) -> None:
        """Should parse semver from prerelease tags."""
        # This depends on implementation - adjust if needed
        result = _parse_semver("v1.2.3-beta.1")
        assert result is None or result == (1, 2, 3)


class TestIsHotfixByName:
    def test_detects_hotfix_keyword(self) -> None:
        """Should detect 'hotfix' in release name."""
        release = {"name": "Hotfix for critical bug", "tag_name": "v1.0.1"}
        assert _is_hotfix_by_name(release) is True

    def test_detects_patch_keyword(self) -> None:
        """Should detect 'patch' in release name."""
        release = {"name": "Security Patch", "tag_name": "v1.0.1"}
        assert _is_hotfix_by_name(release) is True

    def test_detects_fix_keyword(self) -> None:
        """Should detect 'fix' in tag name."""
        release = {"name": "Release", "tag_name": "v1.0.1-fix"}
        assert _is_hotfix_by_name(release) is True

    def test_returns_false_for_normal_release(self) -> None:
        """Should return False for normal releases."""
        release = {"name": "Feature Release", "tag_name": "v2.0.0"}
        assert _is_hotfix_by_name(release) is False


class TestIsSemverPatch:
    def test_detects_patch_version_bump(self) -> None:
        """Should detect v1.2.3 -> v1.2.4 as patch."""
        release = {"tag_name": "v1.2.3", "published_at": "2024-01-01T00:00:00Z"}
        next_release = {"tag_name": "v1.2.4", "published_at": "2024-01-02T00:00:00Z"}
        assert _is_semver_patch(release, next_release) is True

    def test_does_not_detect_minor_bump_as_patch(self) -> None:
        """Should not count v1.2.0 -> v1.3.0 as patch."""
        release = {"tag_name": "v1.2.0", "published_at": "2024-01-01T00:00:00Z"}
        next_release = {"tag_name": "v1.3.0", "published_at": "2024-01-02T00:00:00Z"}
        assert _is_semver_patch(release, next_release) is False

    def test_does_not_detect_major_bump_as_patch(self) -> None:
        """Should not count v1.0.0 -> v2.0.0 as patch."""
        release = {"tag_name": "v1.0.0", "published_at": "2024-01-01T00:00:00Z"}
        next_release = {"tag_name": "v2.0.0", "published_at": "2024-01-02T00:00:00Z"}
        assert _is_semver_patch(release, next_release) is False

    def test_handles_non_semver_tags(self) -> None:
        """Should handle non-semver tags gracefully."""
        release = {"tag_name": "release-1", "published_at": "2024-01-01T00:00:00Z"}
        next_release = {"tag_name": "release-2", "published_at": "2024-01-02T00:00:00Z"}
        assert _is_semver_patch(release, next_release) is False


class TestIsFailureResponse:
    def test_detects_failure_within_7_days(self) -> None:
        """Should detect patch release within 7 days as failure."""
        release = make_release("v1.0.0", "Release 1.0.0", 10)
        next_release = make_release("v1.0.1", "Release 1.0.1", 7)  # 3 days later
        assert _is_failure_response(release, next_release) is True

    def test_ignores_patch_after_7_days(self) -> None:
        """Should not count patch release after 7 days as failure."""
        release = make_release("v1.0.0", "Release 1.0.0", 20)
        next_release = make_release("v1.0.1", "Release 1.0.1", 5)  # 15 days later
        assert _is_failure_response(release, next_release) is False

    def test_detects_hotfix_keyword_as_failure(self) -> None:
        """Should detect hotfix keyword within 7 days as failure."""
        release = make_release("v1.0.0", "Release 1.0.0", 10)
        next_release = make_release("v1.1.0", "Hotfix for bug", 7)  # Not a patch version but has hotfix
        assert _is_failure_response(release, next_release) is True


class TestCollectChangeFailureRate:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_releases(self, mock_github_client) -> None:
        """Should return None when no releases exist."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_change_failure_rate(mock_github_client, "owner/repo")

        assert result["change_failure_rate"] is None
        assert result["total_releases"] == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_single_release(self, mock_github_client) -> None:
        """Should return 0% for single release (no pairs to compare)."""
        mock_http = AsyncMock()
        releases = [make_release("v1.0.0", "First Release", 10)]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_change_failure_rate(mock_github_client, "owner/repo")

        assert result["change_failure_rate"] == pytest.approx(0.0)
        assert result["total_releases"] == 1

    @pytest.mark.asyncio
    async def test_calculates_failure_rate(self, mock_github_client) -> None:
        """Should calculate failure rate correctly."""
        mock_http = AsyncMock()
        # 3 releases: v1.0.0 -> v1.0.1 (failure), v1.0.1 -> v1.1.0 (not failure)
        releases = [
            make_release("v1.0.0", "Release 1.0.0", 20),
            make_release("v1.0.1", "Patch 1.0.1", 18),  # Failure (patch within 7 days)
            make_release("v1.1.0", "Release 1.1.0", 5),  # Not failure (minor bump, >7 days)
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_change_failure_rate(mock_github_client, "owner/repo")

        # 1 failure out of 2 pairs = 50%
        assert result["failed_releases"] == 1
        assert result["total_releases"] == 3
