from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import PortfolioOverviewStagingDB, ProgramAction
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


@pytest.mark.asyncio
async def test_program_candidates_and_suggested_program(db_session: AsyncSession) -> None:
    prog, _, _ = await _seed(db_session)  # _seed creates program "Global Forest Watch (GFW)"
    batch = uuid4()
    await _stage(db_session, batch, "Global Forest Watch")
    matches = await build_matches(db_session, batch)
    m = matches[0]
    assert any(c.id == prog.id for c in m.program_candidates)
    assert m.suggested_program.program_id == prog.id


@pytest.mark.asyncio
async def test_no_program_match_suggests_none(db_session: AsyncSession) -> None:
    await _seed(db_session)
    batch = uuid4()
    await _stage(db_session, batch, "Totally Unrelated XYZ")
    matches = await build_matches(db_session, batch)
    assert matches[0].suggested_program.program_id is None


@pytest.mark.asyncio
async def test_seed_default_links_strong_program(db_session: AsyncSession) -> None:
    from app.core.services.overview_import import get_current_batch, seed_default_decisions

    prog, _, _ = await _seed(db_session)  # creates program "Global Forest Watch (GFW)"
    batch = uuid4()
    row = await _stage(db_session, batch, "Global Forest Watch")
    await seed_default_decisions(db_session, batch)
    await db_session.refresh(row)
    assert row.program_action == ProgramAction.LINK
    assert row.matched_program_id == prog.id
    assert row.matched_project_id is None
    assert row.decided_at is None  # default, not user-touched
    current = await get_current_batch(db_session)
    assert current is not None and current.batch_id == batch


@pytest.mark.asyncio
async def test_seed_default_creates_when_no_program(db_session: AsyncSession) -> None:
    from app.core.services.overview_import import seed_default_decisions

    await _seed(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, "Totally Unrelated XYZ")
    await seed_default_decisions(db_session, batch)
    await db_session.refresh(row)
    assert row.program_action == ProgramAction.CREATE
    assert row.matched_program_id is None
    assert row.new_program_name == "Totally Unrelated XYZ"


@pytest.mark.asyncio
async def test_current_batch_none_when_all_applied(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime

    from app.core.services.overview_import import get_current_batch, seed_default_decisions

    await _seed(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, "Anything")
    await seed_default_decisions(db_session, batch)
    row.applied_at = datetime.now(UTC)
    await db_session.flush()
    assert await get_current_batch(db_session) is None


@pytest.mark.asyncio
async def test_matches_rehydrate_saved_decision(db_session: AsyncSession) -> None:
    from app.core.services.overview_import import save_decision, seed_default_decisions

    prog, _, _ = await _seed(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, "Global Forest Watch")
    await seed_default_decisions(db_session, batch)
    ok = await save_decision(
        db_session,
        batch,
        row.id,
        project_id=None,
        program_action=ProgramAction.LINK,
        program_id=prog.id,
        new_program_name=None,
        user_id=None,
    )
    assert ok is True
    matches = await build_matches(db_session, batch)
    sd = matches[0].saved_decision
    assert sd is not None
    assert sd.program_action == ProgramAction.LINK
    assert sd.program_id == prog.id
    assert sd.project_id is None


@pytest.mark.asyncio
async def test_save_decision_writes_no_domain_rows(db_session: AsyncSession) -> None:
    from sqlalchemy import func as _func

    from app.core.models.portfolio_overview import PortfolioProfileDB
    from app.core.services.overview_import import save_decision

    await _seed(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, "New Thing")
    ok = await save_decision(
        db_session,
        batch,
        row.id,
        project_id=None,
        program_action=ProgramAction.CREATE,
        program_id=None,
        new_program_name="New Thing",
        user_id=None,
    )
    assert ok is True
    profiles = (
        await db_session.execute(select(_func.count()).select_from(PortfolioProfileDB))
    ).scalar_one()
    assert profiles == 0
    await db_session.refresh(row)
    assert row.new_program_name == "New Thing"
    assert row.decided_at is not None


@pytest.mark.asyncio
async def test_save_decision_unknown_row_returns_false(db_session: AsyncSession) -> None:
    from app.core.services.overview_import import save_decision

    ok = await save_decision(
        db_session,
        uuid4(),
        uuid4(),
        project_id=None,
        program_action=ProgramAction.NONE,
        program_id=None,
        new_program_name=None,
        user_id=None,
    )
    assert ok is False
