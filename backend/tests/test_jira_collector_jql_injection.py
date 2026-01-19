"""Tests for JQL injection prevention in Jira collector.

This module tests project key validation to prevent JQL injection attacks
where malicious input could modify JQL queries to access unauthorized data.
"""

import pytest

from app.services.collectors.jira import JiraCollector


class TestJiraCollectorValidateProjectKey:
    """Test project key validation for JQL injection prevention."""

    def test_jira_collector_validate_project_key_valid_uppercase(self) -> None:
        """Valid uppercase project key should be accepted."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("PROJ")
        collector._validate_project_key("ABC")
        collector._validate_project_key("MYPROJECT")

    def test_jira_collector_validate_project_key_valid_with_numbers(self) -> None:
        """Project key with numbers should be accepted."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("PROJ123")
        collector._validate_project_key("ABC1")
        collector._validate_project_key("TEST2026")

    def test_jira_collector_validate_project_key_valid_with_hyphen(self) -> None:
        """Project key with hyphen should be accepted."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("PROJ-SUB")
        collector._validate_project_key("MY-PROJECT")
        collector._validate_project_key("A-B-C")

    def test_jira_collector_validate_project_key_valid_with_underscore(self) -> None:
        """Project key with underscore should be accepted."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("PROJ_SUB")
        collector._validate_project_key("MY_PROJECT")
        collector._validate_project_key("A_B_C")

    def test_jira_collector_validate_project_key_accepts_lowercase(self) -> None:
        """Lowercase project key should be accepted (Jira supports both)."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("proj")
        collector._validate_project_key("fip")
        collector._validate_project_key("myproject")

    def test_jira_collector_validate_project_key_accepts_mixed_case(self) -> None:
        """Mixed case project key should be accepted."""
        collector = JiraCollector()

        # Should not raise exception
        collector._validate_project_key("Proj")
        collector._validate_project_key("FiP")
        collector._validate_project_key("MyProject")
        collector._validate_project_key("Abc123")

    def test_jira_collector_validate_project_key_rejects_special_chars(self) -> None:
        """Project key with SQL injection attempt should be rejected."""
        collector = JiraCollector()

        # SQL/JQL injection attempts
        malicious_keys = [
            "PROJ'; DROP TABLE",
            "PROJ\" OR 1=1",
            "PROJ) OR (1=1",
            "PROJ; DELETE FROM",
            "PROJ'--",
        ]

        for malicious_key in malicious_keys:
            with pytest.raises(ValueError) as exc_info:
                collector._validate_project_key(malicious_key)

            assert "Invalid project key format" in str(exc_info.value)

    def test_jira_collector_validate_project_key_rejects_quotes(self) -> None:
        """Project key with quotes should be rejected."""
        collector = JiraCollector()

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key('PROJ"')

        assert "Invalid project key format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key("PROJ'")

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_collector_validate_project_key_rejects_spaces(self) -> None:
        """Project key with spaces should be rejected."""
        collector = JiraCollector()

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key("PROJ KEY")

        assert "Invalid project key format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key("MY PROJECT")

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_collector_validate_project_key_rejects_too_long(self) -> None:
        """Project key exceeding 20 characters should be rejected."""
        collector = JiraCollector()

        # 21 characters - should be rejected
        long_key = "A" * 21

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key(long_key)

        assert "Invalid project key format" in str(exc_info.value)

    def test_jira_collector_validate_project_key_rejects_empty(self) -> None:
        """Empty project key should be rejected."""
        collector = JiraCollector()

        with pytest.raises(ValueError) as exc_info:
            collector._validate_project_key("")

        assert "Invalid project key format" in str(exc_info.value)


class TestJiraCollectorJQLInjectionPrevention:
    """Test that JQL injection is prevented in actual queries."""

    @pytest.mark.asyncio
    async def test_jira_collector_count_issues_validates_project_key(self) -> None:
        """_count_issues should validate project key before constructing JQL."""
        collector = JiraCollector()

        # Mock client (won't be used if validation fails)
        class MockClient:
            async def post(self, url: str, json: dict) -> None:
                raise AssertionError("Should not reach this point")

        mock_client = MockClient()

        # Attempt injection - should fail validation before query
        with pytest.raises(ValueError) as exc_info:
            await collector._count_issues(
                mock_client, "PROJ'; DROP TABLE users--", "type = Bug"
            )

        assert "Invalid project key format" in str(exc_info.value)
