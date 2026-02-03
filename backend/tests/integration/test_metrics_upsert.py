"""Integration tests for metrics upsert behavior.

These tests verify that the upsert logic works correctly, including
manual field synchronization between snapshot types.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB
from app.models.project import ProjectDB


class TestMetricsUpsertIntegration:
    """Test that metrics upsert behavior works correctly.

    Note: Consolidation of multiple records is no longer supported.
    With the new architecture, only ONE record per (project, year, month, snapshot_type)
    is allowed. Upsert updates existing records rather than creating duplicates.
    """

    @pytest.mark.asyncio
    async def test_upsert_creates_new_record(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify POST creates a new metrics record."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 5,
            },
        )
        assert response.status_code == 201

        data = response.json()
        assert data["governance_exceptions"] == 5

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_record(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify POST updates existing record for same period/type."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create initial record
        response1 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 5,
            },
        )
        assert response1.status_code == 201
        first_id = response1.json()["id"]

        # Update with same period (should upsert, not create new)
        response2 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 1,
            },
        )
        assert response2.status_code == 201
        second_id = response2.json()["id"]

        # Should be the same record
        assert first_id == second_id
        assert response2.json()["governance_exceptions"] == 1

    @pytest.mark.asyncio
    async def test_sev1_incident_caps_quality_score(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify sev1_incident caps P_quality at 60."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create metrics with sev1_incident=True
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            bugs_total=5,
            tasks_completed=100,
            escaped_defects=1,
            mttr_hours=Decimal("24.0"),
            incidents_count=1,
            post_contract_tasks=0,
            sev1_incident=True,
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        # P_quality should be capped at 60 due to sev1
        assert data["scores"]["dimensions"]["p_quality"] <= 60

    @pytest.mark.asyncio
    async def test_manual_fields_sync_to_other_snapshot_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify manual field updates sync to other snapshot type."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create both CUMULATIVE and PUNCTUAL snapshots
        cumulative = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            governance_exceptions=0,
        )
        punctual = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="punctual",
            governance_exceptions=0,
        )
        db_session.add(cumulative)
        db_session.add(punctual)
        await db_session.commit()

        # Update CUMULATIVE with new governance value
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": str(period_start),
                "period_end": str(today),
                "snapshot_type": "cumulative",
                "governance_exceptions": 3,
            },
        )
        assert response.status_code == 201
        assert response.json()["governance_exceptions"] == 3

        # Verify PUNCTUAL was also updated
        await db_session.refresh(punctual)
        assert punctual.governance_exceptions == 3

    @pytest.mark.asyncio
    async def test_manual_fields_sync_milestones(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify milestones sync between snapshot types."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create both snapshots without milestones
        cumulative = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
        )
        punctual = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="punctual",
        )
        db_session.add(cumulative)
        db_session.add(punctual)
        await db_session.commit()

        # Update CUMULATIVE with milestones
        milestones = [
            {"name": "M1", "planned_date": str(today), "actual_date": str(today)},
            {"name": "M2", "planned_date": str(today + timedelta(days=30))},
        ]
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": str(period_start),
                "period_end": str(today),
                "snapshot_type": "cumulative",
                "milestones": milestones,
            },
        )
        assert response.status_code == 201

        # Verify PUNCTUAL was also updated
        await db_session.refresh(punctual)
        assert punctual.milestones is not None
        assert len(punctual.milestones) == 2
        assert punctual.milestones[0]["name"] == "M1"

    @pytest.mark.asyncio
    async def test_non_manual_fields_do_not_sync(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify non-manual fields (like bugs_total) do NOT sync."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create both snapshots
        cumulative = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            bugs_total=10,
        )
        punctual = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="punctual",
            bugs_total=5,
        )
        db_session.add(cumulative)
        db_session.add(punctual)
        await db_session.commit()

        # Update CUMULATIVE with jira_defects (non-manual field)
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": str(period_start),
                "period_end": str(today),
                "snapshot_type": "cumulative",
                "jira_defects": {"bugs_total": 20, "tasks_completed": 100},
            },
        )
        assert response.status_code == 201

        # Verify PUNCTUAL was NOT updated (bugs_total is not manual)
        await db_session.refresh(punctual)
        assert punctual.bugs_total == 5  # Original value preserved
