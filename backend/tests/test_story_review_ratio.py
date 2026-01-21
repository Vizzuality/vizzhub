"""Tests for story_review_ratio indicator.

Tests cover:
- Collection from Jira API
- Calculation formula
- Edge cases (no stories, all with reviewers)
"""

from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.story_review_ratio import (
    calculate_story_review_ratio,
    collect_story_review_ratio,
)


class TestCollectStoryReviewRatio:
    """Test collect_story_review_ratio function."""

    @pytest.mark.asyncio
    async def test_collect_story_review_ratio_calls_correct_jql(self) -> None:
        """Should query done stories and stories with reviewers."""
        mock_client = AsyncMock()
        mock_client.count_issues = AsyncMock(return_value=0)

        await collect_story_review_ratio(mock_client, "PROJ")

        calls = mock_client.count_issues.call_args_list
        assert len(calls) == 2

        # First call: total stories
        assert calls[0][0][0] == "PROJ"
        assert "type = Story" in calls[0][0][1]
        assert "status = Done" in calls[0][0][1]

        # Second call: stories with reviewer
        assert calls[1][0][0] == "PROJ"
        assert "reviewers IS NOT EMPTY" in calls[1][0][1]

    @pytest.mark.asyncio
    async def test_collect_story_review_ratio_returns_counts(self) -> None:
        """Should return total_stories and stories_with_reviewer counts."""
        mock_client = AsyncMock()

        async def mock_count(project, jql):
            if "reviewers IS NOT EMPTY" in jql:
                return 45
            if "type = Story" in jql:
                return 50
            return 0

        mock_client.count_issues = AsyncMock(side_effect=mock_count)

        result = await collect_story_review_ratio(mock_client, "TEST")

        assert result["total_stories"] == 50
        assert result["stories_with_reviewer"] == 45


class TestCalculateStoryReviewRatio:
    """Test calculate_story_review_ratio function."""

    def test_calculate_ratio_basic(self) -> None:
        """Should calculate ratio correctly."""
        result = calculate_story_review_ratio(total_stories=100, stories_with_reviewer=90)
        assert result == 0.9

    def test_calculate_ratio_perfect(self) -> None:
        """All stories with reviewers should return 1.0."""
        result = calculate_story_review_ratio(total_stories=50, stories_with_reviewer=50)
        assert result == 1.0

    def test_calculate_ratio_none(self) -> None:
        """No stories with reviewers should return 0.0."""
        result = calculate_story_review_ratio(total_stories=50, stories_with_reviewer=0)
        assert result == 0.0

    def test_calculate_ratio_no_stories(self) -> None:
        """Zero stories should return None."""
        result = calculate_story_review_ratio(total_stories=0, stories_with_reviewer=0)
        assert result is None

    def test_calculate_ratio_capped_at_one(self) -> None:
        """Should cap at 1.0 even if more reviewers than stories."""
        result = calculate_story_review_ratio(total_stories=10, stories_with_reviewer=15)
        assert result == 1.0

    def test_calculate_ratio_floor_at_zero(self) -> None:
        """Should floor at 0.0 for negative inputs."""
        result = calculate_story_review_ratio(total_stories=10, stories_with_reviewer=-5)
        assert result == 0.0
