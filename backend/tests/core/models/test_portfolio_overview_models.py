from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import (
    MatchAction,
    PortfolioOverviewStagingDB,
    PortfolioProfileDB,
)
from app.core.models.program import ProgramDB


@pytest.mark.asyncio
async def test_staging_and_profile_roundtrip(db_session: AsyncSession) -> None:
    batch = uuid4()
    row = PortfolioOverviewStagingDB(
        import_batch=batch,
        row_index=3,
        name="Global Forest Watch (GFW)",
        client_type_raw="NGO",
        service_raw="All",
        impact_area_raw="Nature, Climate",
        topics_raw="Forest",
        on_website=True,
        is_old_project=False,
        match_action=MatchAction.CREATE,
    )
    db_session.add(row)
    await db_session.flush()

    prog = ProgramDB(name="Global Forest Watch (GFW)")
    db_session.add(prog)
    await db_session.flush()

    profile = PortfolioProfileDB(
        program_id=prog.id, objective="Monitor forests", on_website=True, source_batch=batch
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
    assert got.match_action == MatchAction.CREATE
    assert got.on_website is True
    got_profile = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == prog.id)
        )
    ).scalar_one()
    assert got_profile.objective == "Monitor forests"
