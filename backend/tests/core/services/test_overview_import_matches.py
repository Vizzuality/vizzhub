from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import MatchAction, PortfolioOverviewStagingDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.services.overview_import import build_matches


async def _seed(db: AsyncSession):
    prog = ProgramDB(name="Global Forest Watch (GFW)")
    proj = ProjectDB(name="Airqast", is_billable=True, is_absence=False, status="live")
    db.add_all([prog, proj])
    await db.flush()
    return prog, proj


@pytest.mark.asyncio
async def test_strong_program_match_suggests_link(db_session: AsyncSession) -> None:
    prog, _ = await _seed(db_session)
    batch = uuid4()
    db_session.add(
        PortfolioOverviewStagingDB(
            import_batch=batch, row_index=3, name="Global Forest Watch", is_old_project=False
        )
    )
    await db_session.flush()
    matches = await build_matches(db_session, batch)
    m = matches[0]
    assert m.suggested.action == MatchAction.LINK
    assert m.suggested.program_id == prog.id
    assert any(c.kind == "program" and c.id == prog.id for c in m.candidates)


@pytest.mark.asyncio
async def test_no_match_suggests_create_new(db_session: AsyncSession) -> None:
    await _seed(db_session)
    batch = uuid4()
    db_session.add(
        PortfolioOverviewStagingDB(
            import_batch=batch, row_index=3, name="Totally Unrelated XYZ", is_old_project=False
        )
    )
    await db_session.flush()
    matches = await build_matches(db_session, batch)
    assert matches[0].suggested.action == MatchAction.CREATE
    assert matches[0].suggested.program_id is None
    assert matches[0].suggested.project_id is None


@pytest.mark.asyncio
async def test_old_project_suggests_skip(db_session: AsyncSession) -> None:
    await _seed(db_session)
    batch = uuid4()
    db_session.add(
        PortfolioOverviewStagingDB(
            import_batch=batch, row_index=3, name="Global Forest Watch", is_old_project=True
        )
    )
    await db_session.flush()
    matches = await build_matches(db_session, batch)
    assert matches[0].suggested.action == MatchAction.SKIP
