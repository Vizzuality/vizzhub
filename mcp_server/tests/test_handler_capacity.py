"""Tests for the capacity planner command handler and its summaries."""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.capacity.public import CapacityPlanDB
from mcp_server.data.capacity import current_monday
from mcp_server.handlers.capacity import execute
from mcp_server.services.summary import generate_summary


@pytest_asyncio.fixture
async def people(db_session: AsyncSession) -> dict:
    user = UserDB(
        email="planned@vizzuality.com",
        first_name="Ana",
        last_name="Plan",
        active=True,
        requires_project_reporting=True,
    )
    project = ProjectDB(name="Mangroves", code="MG1", status="live", is_billable=True)
    finished = ProjectDB(name="Old One", code="OLD", status="finished", is_billable=True)
    db_session.add_all([user, project, finished])
    await db_session.flush()
    return {"user": user, "project": project, "finished": finished}


def _weeks(count: int, offset: int = 0) -> list[str]:
    monday = current_monday()
    return [(monday + timedelta(weeks=offset + i)).isoformat() for i in range(count)]


async def _cells(session: AsyncSession, people: dict) -> dict[str, int]:
    rows = (
        await session.execute(
            select(CapacityPlanDB.week_start, CapacityPlanDB.percentage).where(
                CapacityPlanDB.user_id == people["user"].id,
                CapacityPlanDB.project_id == people["project"].id,
            )
        )
    ).all()
    return {r.week_start.isoformat(): r.percentage for r in rows}


def _payload(people: dict, **extra) -> dict:
    return {
        "user_id": str(people["user"].id),
        "project_id": str(people["project"].id),
        **extra,
    }


@pytest.mark.asyncio
async def test_set_allocation_writes_every_week(db_session, people) -> None:
    weeks = _weeks(3)
    result = await execute(
        "set_allocation",
        None,
        _payload(people, percentage=50, weeks=weeks, comment="kick-off"),
        people["user"].id,
        db_session,
    )
    assert result["upserted"] == 3
    assert await _cells(db_session, people) == dict.fromkeys(weeks, 50)


@pytest.mark.asyncio
async def test_set_allocation_zero_clears_weeks(db_session, people) -> None:
    weeks = _weeks(2)
    await execute(
        "set_allocation", None, _payload(people, percentage=80, weeks=weeks),
        people["user"].id, db_session,
    )
    await execute(
        "set_allocation", None, _payload(people, percentage=0, weeks=weeks[:1]),
        people["user"].id, db_session,
    )
    assert await _cells(db_session, people) == {weeks[1]: 80}


@pytest.mark.asyncio
async def test_set_allocation_rejects_past_week_at_execution(db_session, people) -> None:
    with pytest.raises(ValueError, match="future-only"):
        await execute(
            "set_allocation", None, _payload(people, percentage=50, weeks=_weeks(2, offset=-1)),
            people["user"].id, db_session,
        )
    assert await _cells(db_session, people) == {}


@pytest.mark.asyncio
async def test_set_allocation_rejects_finished_project(db_session, people) -> None:
    payload = {
        "user_id": str(people["user"].id),
        "project_id": str(people["finished"].id),
        "percentage": 50,
        "weeks": _weeks(1),
    }
    with pytest.raises(ValueError, match="finished"):
        await execute("set_allocation", None, payload, people["user"].id, db_session)


@pytest.mark.asyncio
async def test_clear_assignment_keeps_earlier_weeks(db_session, people) -> None:
    past_week = current_monday() - timedelta(weeks=2)
    db_session.add(
        CapacityPlanDB(
            project_id=people["project"].id,
            user_id=people["user"].id,
            week_start=past_week,
            percentage=30,
            created_by=people["user"].id,
            updated_by=people["user"].id,
        )
    )
    weeks = _weeks(4)
    await execute(
        "set_allocation", None, _payload(people, percentage=50, weeks=weeks),
        people["user"].id, db_session,
    )

    result = await execute(
        "clear_assignment", None, _payload(people, from_week=weeks[2]),
        people["user"].id, db_session,
    )

    assert result["deleted"] == 2
    assert await _cells(db_session, people) == {
        past_week.isoformat(): 30,
        weeks[0]: 50,
        weeks[1]: 50,
    }


@pytest.mark.asyncio
async def test_unknown_action(db_session, people) -> None:
    with pytest.raises(ValueError, match="Unknown capacity action"):
        await execute("nope", None, {}, people["user"].id, db_session)


@pytest.mark.asyncio
async def test_summaries_use_names(db_session, people) -> None:
    weeks = _weeks(2)
    set_summary = await generate_summary(
        db_session, "capacity", "set_allocation", None,
        _payload(people, percentage=50, weeks=weeks),
    )
    assert set_summary == (
        f"Plan **Ana Plan** at **50%** on **Mangroves** (2 weeks, {weeks[0]} to {weeks[1]})"
    )
    clear_summary = await generate_summary(
        db_session, "capacity", "clear_assignment", None, _payload(people, from_week=weeks[0]),
    )
    assert clear_summary == (
        f"Remove all planned weeks of **Ana Plan** on **Mangroves** from {weeks[0]} onward"
    )
