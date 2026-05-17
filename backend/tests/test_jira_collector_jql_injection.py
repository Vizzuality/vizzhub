"""Tests for JQL injection prevention in Jira collector.

This module tests project key validation to prevent JQL injection attacks
where malicious input could modify JQL queries to access unauthorized data.
"""

import pytest

from app.core.services.jira_client import JiraClient
from app.modules.scorecard.services.collectors.jira import JiraCollector


class TestJiraClientValidateProjectKey:
    """Test project key validation for JQL injection prevention."""

    def test_jira_client_validate_project_key_valid_uppercase(self) -> None:
        """Valid uppercase project key should be accepted."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("PROJ")
        client.validate_project_key("ABC")
        client.validate_project_key("MYPROJECT")

    def test_jira_client_validate_project_key_valid_with_numbers(self) -> None:
        """Project key with numbers should be accepted."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("PROJ123")
        client.validate_project_key("ABC1")
        client.validate_project_key("TEST2026")

    def test_jira_client_validate_project_key_valid_with_hyphen(self) -> None:
        """Project key with hyphen should be accepted."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("PROJ-SUB")
        client.validate_project_key("MY-PROJECT")
        client.validate_project_key("A-B-C")

    def test_jira_client_validate_project_key_valid_with_underscore(self) -> None:
        """Project key with underscore should be accepted."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("PROJ_SUB")
        client.validate_project_key("MY_PROJECT")
        client.validate_project_key("A_B_C")

    def test_jira_client_validate_project_key_accepts_lowercase(self) -> None:
        """Lowercase project key should be accepted (Jira supports both)."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("proj")
        client.validate_project_key("fip")
        client.validate_project_key("myproject")

    def test_jira_client_validate_project_key_accepts_mixed_case(self) -> None:
        """Mixed case project key should be accepted."""
        client = JiraClient()

        # Should not raise exception
        client.validate_project_key("Proj")
        client.validate_project_key("FiP")
        client.validate_project_key("MyProject")
        client.validate_project_key("Abc123")

    def test_jira_client_validate_project_key_rejects_special_chars(self) -> None:
        """Project key with SQL injection attempt should be rejected."""
        client = JiraClient()

        # SQL/JQL injection attempts
        malicious_keys = [
            "PROJ'; DROP TABLE",
            'PROJ" OR 1=1',
            "PROJ) OR (1=1",
            "PROJ; DELETE FROM",
            "PROJ'--",
        ]

        for malicious_key in malicious_keys:
            with pytest.raises(ValueError) as exc_info:
                client.validate_project_key(malicious_key)

            assert "Invalid project key format" in str(exc_info.value)

    def test_jira_client_validate_project_key_rejects_quotes(self) -> None:
        """Project key with quotes should be rejected."""
        client = JiraClient()

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key('PROJ"')

        assert "Invalid project key format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key("PROJ'")

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_client_validate_project_key_rejects_spaces(self) -> None:
        """Project key with spaces should be rejected."""
        client = JiraClient()

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key("PROJ KEY")

        assert "Invalid project key format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key("MY PROJECT")

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_client_validate_project_key_rejects_too_long(self) -> None:
        """Project key exceeding 20 characters should be rejected."""
        client = JiraClient()

        # 21 characters - should be rejected
        long_key = "A" * 21

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key(long_key)

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_client_validate_project_key_rejects_empty(self) -> None:
        """Empty project key should be rejected."""
        client = JiraClient()

        with pytest.raises(ValueError) as exc_info:
            client.validate_project_key("")

        assert "Invalid project key format" in str(exc_info.value)


class TestJiraClientJQLInjectionPrevention:
    """Test that JQL injection is prevented in actual queries."""

    @pytest.mark.asyncio
    async def test_jira_client_count_issues_validates_project_key(self) -> None:
        """count_issues should validate project key before constructing JQL."""
        client = JiraClient()

        # Mock HTTP client (won't be used if validation fails)
        from unittest.mock import AsyncMock

        client._client = AsyncMock()

        # Attempt injection - should fail validation before query
        with pytest.raises(ValueError) as exc_info:
            await client.count_issues("PROJ'; DROP TABLE users--", "type = Bug")

        assert "Invalid project key format" in str(exc_info.value)
        # Should not have made any API calls
        client._client.post.assert_not_called()


class TestJiraCollectorValidatesProjectKey:
    """Test that JiraCollector also validates project keys via JiraClient."""

    @pytest.mark.asyncio
    async def test_jira_collector_collect_validates_project_key(self) -> None:
        """JiraCollector.collect should validate project key before any queries."""
        collector = JiraCollector()

        # Attempt injection - should fail validation
        with pytest.raises(ValueError) as exc_info:
            await collector.collect("PROJ'; DROP TABLE users--")

        assert "Invalid project key format" in str(exc_info.value)
