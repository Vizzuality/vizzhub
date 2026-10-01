"""Internal programs (ops/admin buckets) stay out of the portfolio catalogue by default."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB

from .test_programs_api import viewer  # noqa: F401


async def _seed(db: AsyncSession) -> None:
    client_work = ProgramDB(name="Client Work")
    operations = ProgramDB(name="Operations", is_internal=True)
    db.add_all([client_work, operations])
    await db.flush()
    for program in (client_work, operations):
        db.add(
            ProjectDB(
                name=f"{program.name} 2026",
                status="live",
                program_id=program.id,
                is_billable=program is client_work,
                is_absence=False,
            )
        )
    await db.commit()


@pytest.mark.asyncio
async def test_index_hides_internal_programs_by_default(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    body = (await viewer.get("/api/portfolio/programs")).json()
    assert [p["name"] for p in body["programs"]] == ["Client Work"]
    assert body["total"] == 1
    assert body["programs"][0]["is_internal"] is False

    active = (await viewer.get("/api/portfolio/programs", params={"stage": "Active"})).json()
    assert [p["name"] for p in active["programs"]] == ["Client Work"]


@pytest.mark.asyncio
async def test_index_includes_internal_programs_on_request(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    body = (
        await viewer.get(
            "/api/portfolio/programs", params={"include_internal": "true", "sort": "alpha"}
        )
    ).json()
    assert [(p["name"], p["is_internal"]) for p in body["programs"]] == [
        ("Client Work", False),
        ("Operations", True),
    ]


@pytest.mark.asyncio
async def test_internal_programs_do_not_feed_stage_options(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    internal = ProgramDB(name="Training", is_internal=True)
    db_session.add(internal)
    await db_session.flush()
    db_session.add(
        ProjectDB(
            name="Training 2025",
            status="finished",
            program_id=internal.id,
            is_billable=False,
            is_absence=False,
        )
    )
    await db_session.commit()

    assert (await viewer.get("/api/portfolio/programs/stages")).json() == []


@pytest.mark.asyncio
async def test_internal_program_detail_stays_reachable(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    internal = ProgramDB(name="Operations", is_internal=True)
    db_session.add(internal)
    await db_session.commit()

    resp = await viewer.get(f"/api/portfolio/programs/{internal.id}")
    assert resp.status_code == 200
    assert resp.json()["is_internal"] is True
