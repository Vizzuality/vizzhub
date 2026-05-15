"""Tests for project model.

Tests cover:
- slack_channel_id field existence and behavior
- status whitelist enforcement at ORM-write time
"""

import pytest

from app.core.models.project import (
    ProjectBase,
    ProjectDB,
    ProjectStatus,
    ProjectUpdate,
)


class TestSlackChannelIdField:
    """Test slack_channel_id field on project models."""

    def test_project_db_has_slack_channel_id(self) -> None:
        """ProjectDB should have slack_channel_id attribute."""
        assert hasattr(ProjectDB, "slack_channel_id")

    def test_project_base_has_slack_channel_id(self) -> None:
        """ProjectBase should have slack_channel_id field."""
        project = ProjectBase(name="Test Project", slack_channel_id="C123456")
        assert project.slack_channel_id == "C123456"

    def test_project_base_slack_channel_id_optional(self) -> None:
        """ProjectBase slack_channel_id should be optional."""
        project = ProjectBase(name="Test Project")
        assert project.slack_channel_id is None

    def test_project_update_has_slack_channel_id(self) -> None:
        """ProjectUpdate should have slack_channel_id field."""
        update = ProjectUpdate(slack_channel_id="C123456")
        assert update.slack_channel_id == "C123456"

    def test_project_update_slack_channel_id_optional(self) -> None:
        """ProjectUpdate slack_channel_id should be optional."""
        update = ProjectUpdate()
        assert update.slack_channel_id is None


class TestProjectStatusValidation:
    """Audit Tier 1 #5: ORM-side whitelist on ProjectDB.status.

    Column stays `Mapped[str]` (no migration), but `@validates("status")`
    runs every write through `ProjectStatus(...)` so a typo throws before
    it reaches the DB.
    """

    def test_accepts_enum_value(self) -> None:
        p = ProjectDB(name="X", status=ProjectStatus.LIVE)
        assert p.status == "live"

    def test_accepts_valid_string(self) -> None:
        p = ProjectDB(name="X", status="finished")
        assert p.status == "finished"

    def test_rejects_typo(self) -> None:
        with pytest.raises(ValueError, match="finsihed"):
            ProjectDB(name="X", status="finsihed")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            ProjectDB(name="X", status="")
