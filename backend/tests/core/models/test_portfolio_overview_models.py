from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import (
    PortfolioOverviewStagingDB,
    PortfolioProfileDB,
    ProgramAction,
)
from app.core.models.project import ProjectDB


@pytest.mark.asyncio
async def test_staging_and_profile_roundtrip(db_session: AsyncSession) -> None:
    batch = uuid4()
    row = PortfolioOverviewStagingDB(
        import_batch=batch,
        row_index=3,
        name="Global Forest Watch (GFW)",
        client_type_raw="NGO",
        impact_area_raw="Nature, Climate",
        is_old_project=False,
        program_action=ProgramAction.CREATE,
    )
    db_session.add(row)
    await db_session.flush()

    proj = ProjectDB(name="GFW", is_billable=True, is_absence=False, status="live")
    db_session.add(proj)
    await db_session.flush()

    profile = PortfolioProfileDB(
        project_id=proj.id, objective="Monitor forests", on_website=True, source_batch=batch
    )
    db_session.add(profile)
    await db_session.flush()

    got = (
        await db_session.execute(
            select(PortfolioOverviewStagingDB).where(
                PortfolioOverviewStagingDB.import_batch == batch
            )
        )
    ).scalar_one()
    assert got.program_action == ProgramAction.CREATE
    got_profile = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.project_id == proj.id)
        )
    ).scalar_one()
    assert got_profile.objective == "Monitor forests"


@pytest.mark.asyncio
async def test_profile_program_anchor_roundtrip(db_session: AsyncSession) -> None:
    from app.core.models.program import ProgramDB

    prog = ProgramDB(name="Anchor Program")
    db_session.add(prog)
    await db_session.flush()
    db_session.add(PortfolioProfileDB(program_id=prog.id, objective="Prog-level"))
    await db_session.flush()
    got = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == prog.id)
        )
    ).scalar_one()
    assert got.project_id is None
    assert got.objective == "Prog-level"


@pytest.mark.asyncio
async def test_profile_rejects_both_null(db_session: AsyncSession) -> None:
    import pytest as _pytest
    from sqlalchemy.exc import IntegrityError

    db_session.add(PortfolioProfileDB(objective="orphan"))
    with _pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_staging_draft_columns_roundtrip(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.core.models.portfolio_overview import (
        PortfolioOverviewStagingDB,
        ProgramAction,
    )

    batch = uuid4()
    now = datetime.now(UTC)
    db_session.add(
        PortfolioOverviewStagingDB(
            import_batch=batch,
            row_index=1,
            name="Row A",
            program_action=ProgramAction.CREATE,
            new_program_name="Row A",
            applied_at=now,
        )
    )
    await db_session.flush()
    got = (
        await db_session.execute(
            select(PortfolioOverviewStagingDB).where(
                PortfolioOverviewStagingDB.import_batch == batch
            )
        )
    ).scalar_one()
    assert got.new_program_name == "Row A"
    assert got.applied_at is not None
