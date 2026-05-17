"""Tests for Silences API endpoints."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB, AlertSilenceDB


class TestListSilences:
    """Tests for GET /api/silences endpoint."""

    @pytest.mark.asyncio
    async def test_list_silences_empty(self, client: AsyncClient) -> None:
        """List silences returns empty list when none exist."""
        response = await client.get("/api/silences")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_silences_returns_all(self, client: AsyncClient, db_session) -> None:
        """List silences returns all active silences."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        silence1 = AlertSilenceDB(
            project_id=project.id,
            reason="Maintenance",
            created_by="user1",
        )
        silence2 = AlertSilenceDB(
            project_id=project.id,
            reason="Holiday",
            created_by="user2",
        )
        db_session.add_all([silence1, silence2])
        await db_session.commit()

        response = await client.get("/api/silences")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_silences_filter_by_project(self, client: AsyncClient, db_session) -> None:
        """List silences filters by project_id."""
        project1 = ProjectDB(
            id=uuid4(),
            name="Project 1",
            jira_project_key="P1",
        )
        project2 = ProjectDB(
            id=uuid4(),
            name="Project 2",
            jira_project_key="P2",
        )
        db_session.add_all([project1, project2])
        await db_session.commit()

        silence1 = AlertSilenceDB(project_id=project1.id, reason="Test 1")
        silence2 = AlertSilenceDB(project_id=project2.id, reason="Test 2")
        db_session.add_all([silence1, silence2])
        await db_session.commit()

        response = await client.get(f"/api/silences?project_id={project1.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["reason"] == "Test 1"

    @pytest.mark.asyncio
    async def test_list_silences_excludes_expired_by_default(
        self, client: AsyncClient, db_session
    ) -> None:
        """List silences excludes expired silences by default."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        now = datetime.now(UTC)
        active_silence = AlertSilenceDB(
            project_id=project.id,
            silenced_until=now + timedelta(days=1),
            reason="Active",
        )
        expired_silence = AlertSilenceDB(
            project_id=project.id,
            silenced_until=now - timedelta(days=1),
            reason="Expired",
        )
        indefinite_silence = AlertSilenceDB(
            project_id=project.id,
            silenced_until=None,
            reason="Indefinite",
        )
        db_session.add_all([active_silence, expired_silence, indefinite_silence])
        await db_session.commit()

        response = await client.get("/api/silences")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        reasons = [s["reason"] for s in data]
        assert "Active" in reasons
        assert "Indefinite" in reasons
        assert "Expired" not in reasons

    @pytest.mark.asyncio
    async def test_list_silences_include_expired(self, client: AsyncClient, db_session) -> None:
        """List silences includes expired when flag is set."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        now = datetime.now(UTC)
        expired_silence = AlertSilenceDB(
            project_id=project.id,
            silenced_until=now - timedelta(days=1),
            reason="Expired",
        )
        db_session.add(expired_silence)
        await db_session.commit()

        response = await client.get("/api/silences?include_expired=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["reason"] == "Expired"

    @pytest.mark.asyncio
    async def test_list_silences_includes_related_names(
        self, client: AsyncClient, db_session
    ) -> None:
        """List silences includes project and alert names."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project, alert])
        await db_session.commit()
        await db_session.refresh(alert)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            reason="Test",
        )
        db_session.add(silence)
        await db_session.commit()

        response = await client.get("/api/silences")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["project_name"] == "Test Project"
        assert data[0]["alert_name"] == "test_alert"


class TestCreateSilence:
    """Tests for POST /api/silences endpoint."""

    @pytest.mark.asyncio
    async def test_create_silence_success(self, client: AsyncClient, db_session) -> None:
        """Create silence successfully."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(
            "/api/silences",
            json={
                "project_id": str(project.id),
                "reason": "Maintenance window",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == str(project.id)
        assert data["reason"] == "Maintenance window"
        assert data["project_name"] == "Test Project"
        assert data["alert_definition_id"] is None
        assert data["alert_name"] is None
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_silence_with_alert_definition(
        self, client: AsyncClient, db_session
    ) -> None:
        """Create silence for specific alert definition."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        alert = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project, alert])
        await db_session.commit()
        await db_session.refresh(alert)

        response = await client.post(
            "/api/silences",
            json={
                "project_id": str(project.id),
                "alert_definition_id": alert.id,
                "reason": "Known issue",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alert_definition_id"] == alert.id
        assert data["alert_name"] == "score_drop"

    @pytest.mark.asyncio
    async def test_create_silence_with_expiry(self, client: AsyncClient, db_session) -> None:
        """Create silence with expiry date."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        expiry = datetime.now(UTC) + timedelta(days=7)
        response = await client.post(
            "/api/silences",
            json={
                "project_id": str(project.id),
                "silenced_until": expiry.isoformat(),
                "reason": "Sprint end",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["silenced_until"] is not None

    @pytest.mark.asyncio
    async def test_create_silence_project_not_found(self, client: AsyncClient) -> None:
        """Create silence returns 404 for non-existent project."""
        fake_id = str(uuid4())
        response = await client.post(
            "/api/silences",
            json={
                "project_id": fake_id,
                "reason": "Test",
            },
        )
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_silence_alert_not_found(self, client: AsyncClient, db_session) -> None:
        """Create silence returns 404 for non-existent alert definition."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(
            "/api/silences",
            json={
                "project_id": str(project.id),
                "alert_definition_id": 99999,
                "reason": "Test",
            },
        )
        assert response.status_code == 404
        assert "Alert definition not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_silence_invalid_project_id(self, client: AsyncClient) -> None:
        """Create silence returns 400 for invalid project ID format."""
        response = await client.post(
            "/api/silences",
            json={
                "project_id": "not-a-uuid",
                "reason": "Test",
            },
        )
        assert response.status_code == 400
        assert "Invalid project ID format" in response.json()["detail"]


class TestUpdateSilence:
    """Tests for PUT /api/silences{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_silence_success(self, client: AsyncClient, db_session) -> None:
        """Update silence successfully."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        silence = AlertSilenceDB(
            project_id=project.id,
            reason="Original reason",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        new_expiry = datetime.now(UTC) + timedelta(days=14)
        response = await client.put(
            f"/api/silences/{silence.id}",
            json={
                "silenced_until": new_expiry.isoformat(),
                "reason": "Updated reason",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reason"] == "Updated reason"
        assert data["silenced_until"] is not None

    @pytest.mark.asyncio
    async def test_update_silence_partial(self, client: AsyncClient, db_session) -> None:
        """Update silence with partial data."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        silence = AlertSilenceDB(
            project_id=project.id,
            reason="Original reason",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        response = await client.put(
            f"/api/silences/{silence.id}",
            json={"reason": "Only reason updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reason"] == "Only reason updated"

    @pytest.mark.asyncio
    async def test_update_silence_not_found(self, client: AsyncClient) -> None:
        """Update silence returns 404 for non-existent silence."""
        response = await client.put(
            "/api/silences/99999",
            json={"reason": "New reason"},
        )
        assert response.status_code == 404
        assert "Silence not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_silence_includes_related_names(
        self, client: AsyncClient, db_session
    ) -> None:
        """Update silence response includes project and alert names."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project, alert])
        await db_session.commit()
        await db_session.refresh(alert)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            reason="Test",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        response = await client.put(
            f"/api/silences/{silence.id}",
            json={"reason": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["project_name"] == "Test Project"
        assert data["alert_name"] == "test_alert"


class TestDeleteSilence:
    """Tests for DELETE /api/silences{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_silence_success(self, client: AsyncClient, db_session) -> None:
        """Delete silence successfully."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        silence = AlertSilenceDB(
            project_id=project.id,
            reason="To be deleted",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        response = await client.delete(f"/api/silences/{silence.id}")
        assert response.status_code == 204

        get_response = await client.get("/api/silences?include_expired=true")
        assert get_response.status_code == 200
        assert len(get_response.json()) == 0

    @pytest.mark.asyncio
    async def test_delete_silence_not_found(self, client: AsyncClient) -> None:
        """Delete silence returns 404 for non-existent silence."""
        response = await client.delete("/api/silences/99999")
        assert response.status_code == 404
        assert "Silence not found" in response.json()["detail"]
