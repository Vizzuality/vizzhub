from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.project import ProjectDB


@pytest.mark.asyncio
async def test_profile_project_anchor_roundtrip(db_session: AsyncSession) -> None:
    batch = uuid4()
    proj = ProjectDB(name="GFW", is_billable=True, is_absence=False, status="live")
    db_session.add(proj)
    await db_session.flush()

    db_session.add(
        PortfolioProfileDB(
            project_id=proj.id, objective="Monitor forests", on_website=True, source_batch=batch
        )
    )
    await db_session.flush()

    got = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.project_id == proj.id)
        )
    ).scalar_one()
    assert got.objective == "Monitor forests"
    assert got.on_website is True
    assert got.source_batch == batch


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
    from sqlalchemy.exc import IntegrityError

    db_session.add(PortfolioProfileDB(objective="orphan"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_search_vector_generated_and_queryable(db_session: AsyncSession) -> None:
    """create_all must produce the same generated tsvector column as migration 099."""
    from app.core.models.program import ProgramDB

    program = ProgramDB(name="Vector Program")
    db_session.add(program)
    await db_session.flush()
    db_session.add(
        PortfolioProfileDB(
            program_id=program.id,
            objective="Restoring mangrove ecosystems in coastal areas",
        )
    )
    await db_session.commit()

    match = (
        (
            await db_session.execute(
                select(PortfolioProfileDB.program_id).where(
                    PortfolioProfileDB.search_vector.op("@@")(
                        func.websearch_to_tsquery("english", "restoration mangroves")
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    assert match == [program.id]
