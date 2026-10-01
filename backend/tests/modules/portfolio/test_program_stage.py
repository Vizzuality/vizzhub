"""Program stage is derived from its projects, not trusted from the stored profile."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.services.program_catalog import derive_program_stage

from .test_programs_api import viewer  # noqa: F401


@pytest.mark.parametrize(
    ("stored", "statuses", "expected"),
    [
        ("Active", ["finished", "finished"], "Finished"),
        ("Finished", ["finished", "live"], "Active"),
        (None, ["live"], "Active"),
        ("Maintenance", ["live"], "Maintenance"),
        ("Maintenance", ["finished"], "Finished"),
        ("Active", ["proposal"], "Active"),
        ("Active", [], "Active"),
        (None, [], None),
    ],
)
def test_derive_program_stage(stored: str | None, statuses: list[str], expected: str | None):
    assert derive_program_stage(stored, statuses) == expected


async def _program(
    db: AsyncSession, name: str, stored: str | None, statuses: list[str], *, profile: bool = True
) -> ProgramDB:
    program = ProgramDB(name=name)
    db.add(program)
    await db.flush()
    if profile:
        db.add(PortfolioProfileDB(program_id=program.id, stage=stored))
    for i, status in enumerate(statuses):
        db.add(
            ProjectDB(
                name=f"{name} {i}",
                status=status,
                program_id=program.id,
                is_billable=True,
                is_absence=False,
            )
        )
    await db.flush()
    return program


@pytest.mark.asyncio
async def test_index_stage_filter_and_display_follow_projects(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _program(db_session, "Stale Active", "Active", ["finished", "finished"])
    await _program(db_session, "Stale Finished", "Finished", ["finished", "live"])
    await _program(db_session, "Maint Live", "Maintenance", ["live"])
    await _program(db_session, "Maint Done", "Maintenance", ["finished"])
    await _program(db_session, "Legacy", "Active", [])
    await _program(db_session, "No Profile", None, ["live"], profile=False)
    await db_session.commit()

    resp = await viewer.get("/api/portfolio/programs", params={"n": 50})
    stages = {p["name"]: p["stage"] for p in resp.json()["programs"]}
    assert stages == {
        "Stale Active": "Finished",
        "Stale Finished": "Active",
        "Maint Live": "Maintenance",
        "Maint Done": "Finished",
        "Legacy": "Active",
        "No Profile": "Active",
    }

    for stage in ("Active", "Finished", "Maintenance"):
        resp = await viewer.get("/api/portfolio/programs", params={"stage": stage, "n": 50})
        names = {p["name"] for p in resp.json()["programs"]}
        assert names == {n for n, s in stages.items() if s == stage}, stage

    resp = await viewer.get("/api/portfolio/programs/stages")
    assert resp.json() == ["Active", "Finished", "Maintenance"]


@pytest.mark.asyncio
async def test_detail_exposes_derived_stage(
    viewer: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    program = await _program(db_session, "Stale Active", "Active", ["finished"])
    await db_session.commit()

    body = (await viewer.get(f"/api/portfolio/programs/{program.id}")).json()
    assert body["stage"] == "Finished"
    assert body["profile"]["stage"] == "Active"  # stored value kept as the manual input
