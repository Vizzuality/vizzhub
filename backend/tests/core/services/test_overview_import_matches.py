from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import PortfolioOverviewStagingDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.services.overview_import import build_matches


async def _seed(db: AsyncSession):
    prog = ProgramDB(name="Global Forest Watch (GFW)")
    db.add(prog)
    await db.flush()
    linked = ProjectDB(
        name="Global Forest Watch platform",
        is_billable=True,
        is_absence=False,
        status="live",
        program_id=prog.id,
    )
    standalone = ProjectDB(name="Airqast", is_billable=True, is_absence=False, status="live")
    db.add_all([linked, standalone])
    await db.flush()
    return prog, linked, standalone


async def _stage(db, batch, name, old=False):
    row = PortfolioOverviewStagingDB(import_batch=batch, row_index=3, name=name, is_old_project=old)
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_strong_project_match_and_current_program(db_session: AsyncSession) -> None:
    prog, linked, _ = await _seed(db_session)
    batch = uuid4()
    await _stage(db_session, batch, "Global Forest Watch platform")
    matches = await build_matches(db_session, batch)
    m = matches[0]
    assert m.suggested_project.project_id == linked.id
    assert m.current_program.program_id == prog.id
    assert m.current_program.name == "Global Forest Watch (GFW)"
    assert any(c.id == linked.id for c in m.project_candidates)


@pytest.mark.asyncio
async def test_standalone_project_has_no_current_program(db_session: AsyncSession) -> None:
    _, _, standalone = await _seed(db_session)
    batch = uuid4()
    await _stage(db_session, batch, "Airqast")
    matches = await build_matches(db_session, batch)
    m = matches[0]
    assert m.suggested_project.project_id == standalone.id
    assert m.current_program.program_id is None


@pytest.mark.asyncio
async def test_no_project_match_suggests_none(db_session: AsyncSession) -> None:
    await _seed(db_session)
    batch = uuid4()
    await _stage(db_session, batch, "Totally Unrelated XYZ")
    matches = await build_matches(db_session, batch)
    assert matches[0].suggested_project.project_id is None
