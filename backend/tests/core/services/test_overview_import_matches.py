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


@pytest.mark.asyncio
async def test_strong_project_match_suggests_create_from_project(db_session: AsyncSession) -> None:
    """When best program candidate is below STRONG but a standalone project scores >= STRONG,
    _suggest returns CREATE with project_id set (not a CREATE-new with both IDs None)."""
    prog, proj = await _seed(db_session)
    batch = uuid4()
    db_session.add(
        PortfolioOverviewStagingDB(
            import_batch=batch, row_index=4, name="Airqast", is_old_project=False
        )
    )
    await db_session.flush()
    matches = await build_matches(db_session, batch)
    m = matches[0]
    # The standalone project "Airqast" must score >= STRONG (0.85) against the row name "Airqast"
    airqast_candidate = next((c for c in m.candidates if c.id == proj.id), None)
    assert airqast_candidate is not None, "Airqast project must appear in candidates"
    assert airqast_candidate.score >= 0.85, (
        f"Expected Airqast to score >= 0.85, got {airqast_candidate.score}"
    )
    # The program "Global Forest Watch (GFW)" must score below STRONG for this row
    gfw_candidate = next((c for c in m.candidates if c.id == prog.id), None)
    if gfw_candidate is not None:
        assert gfw_candidate.score < 0.85, (
            f"Expected GFW program to score < 0.85 for 'Airqast', got {gfw_candidate.score}"
        )
    # Suggestion must be CREATE-from-project (project_id set, program_id None)
    assert m.suggested.action == MatchAction.CREATE
    assert m.suggested.project_id == proj.id
    assert m.suggested.program_id is None
