"""Tests for Notifications API endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.project import ProjectDB
from app.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    DependabotAlertTrackedDB,
)


class TestListNotifications:
    """Tests for GET /api/notifications endpoint."""

    @pytest.mark.asyncio
    async def test_list_notifications_empty(self, client: AsyncClient) -> None:
        """List notifications returns empty list when none exist."""
        response = await client.get("/api/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["pages"] == 0

    @pytest.mark.asyncio
    async def test_list_notifications_returns_all(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications returns all notifications."""
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

        notification1 = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Test message 1",
            status="sent",
        )
        notification2 = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Test message 2",
            status="sent",
        )
        db_session.add_all([notification1, notification2])
        await db_session.commit()

        response = await client.get("/api/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["pages"] == 1

    @pytest.mark.asyncio
    async def test_list_notifications_filter_by_project(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications filters by project_id."""
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
        alert = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project1, project2, alert])
        await db_session.commit()
        await db_session.refresh(alert)

        notification1 = AlertNotificationDB(
            project_id=project1.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Message for P1",
            status="sent",
        )
        notification2 = AlertNotificationDB(
            project_id=project2.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Message for P2",
            status="sent",
        )
        db_session.add_all([notification1, notification2])
        await db_session.commit()

        response = await client.get(f"/api/notifications/?project_id={project1.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["message"] == "Message for P1"
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_notifications_filter_by_alert_definition(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications filters by alert_definition_id."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        alert1 = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        alert2 = AlertDefinitionDB(
            name="dependabot",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project, alert1, alert2])
        await db_session.commit()
        await db_session.refresh(alert1)
        await db_session.refresh(alert2)

        notification1 = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert1.id,
            channel_id="C123",
            message="Score drop alert",
            status="sent",
        )
        notification2 = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert2.id,
            channel_id="C123",
            message="Dependabot alert",
            status="sent",
        )
        db_session.add_all([notification1, notification2])
        await db_session.commit()

        response = await client.get(f"/api/notifications/?alert_definition_id={alert1.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["message"] == "Score drop alert"

    @pytest.mark.asyncio
    async def test_list_notifications_filter_by_date_range(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications filters by date range."""
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

        now = datetime.now(timezone.utc)
        recent_notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Recent notification",
            status="sent",
            sent_at=now,
        )
        old_notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Old notification",
            status="sent",
            sent_at=now - timedelta(days=30),
        )
        db_session.add_all([recent_notification, old_notification])
        await db_session.commit()

        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = await client.get(
            f"/api/notifications/?start_date={start_date}&end_date={end_date}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["message"] == "Recent notification"

    @pytest.mark.asyncio
    async def test_list_notifications_pagination(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications supports pagination."""
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

        now = datetime.now(timezone.utc)
        notifications = [
            AlertNotificationDB(
                project_id=project.id,
                alert_definition_id=alert.id,
                channel_id="C123",
                message=f"Notification {i}",
                status="sent",
                sent_at=now - timedelta(minutes=i),
            )
            for i in range(15)
        ]
        db_session.add_all(notifications)
        await db_session.commit()

        response = await client.get("/api/notifications/?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 15
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert data["pages"] == 3

        response = await client.get("/api/notifications/?page=2&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 2

        response = await client.get("/api/notifications/?page=3&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 3

    @pytest.mark.asyncio
    async def test_list_notifications_includes_related_names(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications includes project and alert names."""
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

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Test message",
            status="sent",
        )
        db_session.add(notification)
        await db_session.commit()

        response = await client.get("/api/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["project_name"] == "Test Project"
        assert data["items"][0]["alert_name"] == "score_drop"

    @pytest.mark.asyncio
    async def test_list_notifications_includes_error_info(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications includes error message for failed notifications."""
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

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Test message",
            status="failed",
            error_message="Channel not found",
        )
        db_session.add(notification)
        await db_session.commit()

        response = await client.get("/api/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "failed"
        assert data["items"][0]["error_message"] == "Channel not found"

    @pytest.mark.asyncio
    async def test_list_notifications_sorted_by_sent_at_desc(
        self, client: AsyncClient, db_session
    ) -> None:
        """List notifications is sorted by sent_at descending (newest first)."""
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

        now = datetime.now(timezone.utc)
        notification_old = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Old notification",
            status="sent",
            sent_at=now - timedelta(hours=2),
        )
        notification_new = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="New notification",
            status="sent",
            sent_at=now,
        )
        db_session.add_all([notification_old, notification_new])
        await db_session.commit()

        response = await client.get("/api/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["message"] == "New notification"
        assert data["items"][1]["message"] == "Old notification"

    @pytest.mark.asyncio
    async def test_list_notifications_page_size_limit(
        self, client: AsyncClient
    ) -> None:
        """List notifications enforces max page_size of 100."""
        response = await client.get("/api/notifications/?page_size=150")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_notifications_page_minimum(
        self, client: AsyncClient
    ) -> None:
        """List notifications enforces min page of 1."""
        response = await client.get("/api/notifications/?page=0")
        assert response.status_code == 400


class TestNotificationStats:
    """Tests for GET /api/notifications/stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, client: AsyncClient) -> None:
        """Stats returns zeros when no notifications exist."""
        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_this_month"] == 0
        assert data["by_type"] == {}
        assert data["by_project"] == []
        assert data["avg_vulnerability_resolution_days"] is None

    @pytest.mark.asyncio
    async def test_stats_total_this_month(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats counts notifications from current month only."""
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

        now = datetime.now(timezone.utc)
        this_month = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="This month",
            status="sent",
            sent_at=now,
        )
        last_month = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Last month",
            status="sent",
            sent_at=now - timedelta(days=32),
        )
        failed = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123",
            message="Failed this month",
            status="failed",
            sent_at=now,
        )
        db_session.add_all([this_month, last_month, failed])
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_this_month"] == 1

    @pytest.mark.asyncio
    async def test_stats_by_type(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats groups notifications by alert type."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        alert1 = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        alert2 = AlertDefinitionDB(
            name="dependabot",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project, alert1, alert2])
        await db_session.commit()
        await db_session.refresh(alert1)
        await db_session.refresh(alert2)

        now = datetime.now(timezone.utc)
        notifications = [
            AlertNotificationDB(
                project_id=project.id,
                alert_definition_id=alert1.id,
                channel_id="C123",
                message=f"Score drop {i}",
                status="sent",
                sent_at=now,
            )
            for i in range(3)
        ] + [
            AlertNotificationDB(
                project_id=project.id,
                alert_definition_id=alert2.id,
                channel_id="C123",
                message=f"Dependabot {i}",
                status="sent",
                sent_at=now,
            )
            for i in range(2)
        ]
        db_session.add_all(notifications)
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["by_type"]["score_drop"] == 3
        assert data["by_type"]["dependabot"] == 2

    @pytest.mark.asyncio
    async def test_stats_by_project(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats groups notifications by project."""
        project1 = ProjectDB(
            id=uuid4(),
            name="Project Alpha",
            jira_project_key="PA",
        )
        project2 = ProjectDB(
            id=uuid4(),
            name="Project Beta",
            jira_project_key="PB",
        )
        alert = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add_all([project1, project2, alert])
        await db_session.commit()
        await db_session.refresh(alert)

        now = datetime.now(timezone.utc)
        notifications = [
            AlertNotificationDB(
                project_id=project1.id,
                alert_definition_id=alert.id,
                channel_id="C123",
                message=f"Alpha {i}",
                status="sent",
                sent_at=now,
            )
            for i in range(5)
        ] + [
            AlertNotificationDB(
                project_id=project2.id,
                alert_definition_id=alert.id,
                channel_id="C123",
                message=f"Beta {i}",
                status="sent",
                sent_at=now,
            )
            for i in range(2)
        ]
        db_session.add_all(notifications)
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert len(data["by_project"]) == 2
        project_counts = {p["project_name"]: p["count"] for p in data["by_project"]}
        assert project_counts["Project Alpha"] == 5
        assert project_counts["Project Beta"] == 2

    @pytest.mark.asyncio
    async def test_stats_avg_vulnerability_resolution(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats calculates average vulnerability resolution time."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        resolved_alert1 = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=1,
            package_name="lodash",
            severity="high",
            first_seen_at=now - timedelta(days=10),
            resolved_at=now,
        )
        resolved_alert2 = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=2,
            package_name="axios",
            severity="medium",
            first_seen_at=now - timedelta(days=20),
            resolved_at=now,
        )
        unresolved_alert = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=3,
            package_name="express",
            severity="critical",
            first_seen_at=now - timedelta(days=5),
            resolved_at=None,
        )
        db_session.add_all([resolved_alert1, resolved_alert2, unresolved_alert])
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["avg_vulnerability_resolution_days"] == pytest.approx(15.0)

    @pytest.mark.asyncio
    async def test_stats_avg_vulnerability_resolution_no_resolved(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats returns None for avg resolution when no alerts are resolved."""
        project = ProjectDB(
            id=uuid4(),
            name="Test Project",
            jira_project_key="TEST",
        )
        db_session.add(project)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        unresolved_alert = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=1,
            package_name="lodash",
            severity="high",
            first_seen_at=now - timedelta(days=10),
            resolved_at=None,
        )
        db_session.add(unresolved_alert)
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["avg_vulnerability_resolution_days"] is None

    @pytest.mark.asyncio
    async def test_stats_by_project_top_10(
        self, client: AsyncClient, db_session
    ) -> None:
        """Stats by_project returns only top 10 projects."""
        alert = AlertDefinitionDB(
            name="score_drop",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        projects = []
        for i in range(12):
            p = ProjectDB(
                id=uuid4(),
                name=f"Project {i:02d}",
                jira_project_key=f"P{i:02d}",
            )
            projects.append(p)
        db_session.add_all(projects)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        notifications = []
        for i, project in enumerate(projects):
            for j in range(i + 1):
                notifications.append(
                    AlertNotificationDB(
                        project_id=project.id,
                        alert_definition_id=alert.id,
                        channel_id="C123",
                        message=f"Notification for {project.name}",
                        status="sent",
                        sent_at=now,
                    )
                )
        db_session.add_all(notifications)
        await db_session.commit()

        response = await client.get("/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert len(data["by_project"]) == 10
        assert data["by_project"][0]["count"] >= data["by_project"][-1]["count"]
