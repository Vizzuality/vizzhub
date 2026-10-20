"""Project delete vs tracker references: logged time and progress block, empty parts don't."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models import (
    ProgressReportDB,
    ReportDB,
    ReportingPeriodDB,
    ReportPartDB,
)


@pytest_asyncio.fixture
async def report(db_session: AsyncSession, default_program: str) -> ReportDB:
    user = UserDB(email="reporter@test.com", first_name="Re", last_name="Porter", active=True)
    period = ReportingPeriodDB(date=dt.date(2026, 1, 1), status="finished")
    db_session.add_all([user, period])
    await db_session.flush()
    report = ReportDB(user_id=user.id, reporting_period_id=period.id)
    db_session.add(report)
    await db_session.flush()
    return report


async def _project(db_session: AsyncSession, program_id: str) -> ProjectDB:
    project = ProjectDB(name="Refs", code="REFS", program_id=program_id, status="finished")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_empty_report_parts_do_not_block_delete_and_are_removed(
    client: AsyncClient, db_session: AsyncSession, report: ReportDB, default_program: str
) -> None:
    project = await _project(db_session, default_program)
    db_session.add_all(
        [
            ReportPartDB(report_id=report.id, project_id=project.id, percentage=None),
            ReportPartDB(report_id=report.id, project_id=project.id, percentage=Decimal("0")),
        ]
    )
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}")

    assert response.status_code == 204
    remaining = await db_session.scalar(
        select(func.count()).select_from(ReportPartDB).where(ReportPartDB.project_id == project.id)
    )
    assert remaining == 0


@pytest.mark.asyncio
async def test_logged_time_blocks_delete(
    client: AsyncClient, db_session: AsyncSession, report: ReportDB, default_program: str
) -> None:
    project = await _project(db_session, default_program)
    db_session.add_all(
        [
            ReportPartDB(report_id=report.id, project_id=project.id, percentage=Decimal("0.2500")),
            ReportPartDB(report_id=report.id, project_id=project.id, percentage=None),
        ]
    )
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot delete: project has 1 time report entry."


@pytest.mark.asyncio
async def test_progress_report_blocks_delete(
    client: AsyncClient, db_session: AsyncSession, report: ReportDB, default_program: str
) -> None:
    project = await _project(db_session, default_program)
    db_session.add(
        ProgressReportDB(
            reporting_period_id=report.reporting_period_id,
            project_id=project.id,
            percentage=Decimal("0.0050"),
            delta=Decimal("0"),
        )
    )
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot delete: project has 1 progress report."
