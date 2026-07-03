from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_overview import (
    MatchAction,
    PortfolioOverviewStagingDB,
    PortfolioProfileDB,
)
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.services.overview_import import DecisionInput, apply_decisions


async def _seed_taxonomies(db: AsyncSession) -> None:
    ct = TaxonomyDB(
        slug="client-type", name="Client type", cardinality="single", allows_primary=False
    )
    impact = TaxonomyDB(
        slug="impact-area", name="Impact area", cardinality="multi", allows_primary=True
    )
    topics = TaxonomyDB(slug="topics", name="Topics", cardinality="multi", allows_primary=False)
    db.add_all([ct, impact, topics])
    await db.flush()
    db.add_all(
        [
            TaxonomyTermDB(taxonomy_id=ct.id, slug="ngo", name="NGO"),
            TaxonomyTermDB(taxonomy_id=impact.id, slug="nature", name="Nature"),
            TaxonomyTermDB(taxonomy_id=impact.id, slug="climate", name="Climate"),
        ]
    )
    await db.flush()


async def _stage(db: AsyncSession, batch, **kw) -> PortfolioOverviewStagingDB:
    row = PortfolioOverviewStagingDB(
        import_batch=batch, row_index=3, name=kw.pop("name", "X"), **kw
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_create_new_program_writes_profile_and_terms(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    batch = uuid4()
    row = await _stage(
        db_session,
        batch,
        name="Brand New Program",
        client_type_raw="NGO",
        impact_area_raw="Nature, Climate",
        topics_raw="Forest",
        objective="Save forests",
    )
    result = await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, action=MatchAction.CREATE)],
        user_id=None,
    )
    assert result.created_programs == 1
    prog = (
        await db_session.execute(select(ProgramDB).where(ProgramDB.name == "Brand New Program"))
    ).scalar_one()
    profile = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == prog.id)
        )
    ).scalar_one()
    assert profile.objective == "Save forests"
    term_count = (
        await db_session.execute(
            select(func.count()).select_from(EntityTermDB).where(EntityTermDB.program_id == prog.id)
        )
    ).scalar_one()
    assert term_count == 4  # NGO + Nature + Climate + Forest(created)
    forest = (
        await db_session.execute(select(TaxonomyTermDB).where(TaxonomyTermDB.name == "Forest"))
    ).scalar_one()
    assert forest.slug == "forest"


@pytest.mark.asyncio
async def test_unknown_controlled_term_reported_not_created(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, name="P2", impact_area_raw="Nature, Unicorns")
    result = await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, action=MatchAction.CREATE)],
        user_id=None,
    )
    assert any("Unicorns" in u for u in result.unmapped_terms)


@pytest.mark.asyncio
async def test_create_from_project_sets_program_id(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    proj = ProjectDB(name="Airqast", is_billable=True, is_absence=False, status="live")
    db_session.add(proj)
    await db_session.flush()
    batch = uuid4()
    row = await _stage(db_session, batch, name="Airqast")
    await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, action=MatchAction.CREATE, project_id=proj.id)],
        user_id=None,
    )
    await db_session.refresh(proj)
    assert proj.program_id is not None


@pytest.mark.asyncio
async def test_client_cascade_only_fills_null(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    client = ClientDB(name="World Resources Institute", slug="world-resources-institute")
    db_session.add(client)
    prog = ProgramDB(name="GFW")
    db_session.add(prog)
    await db_session.flush()
    filled = ClientDB(name="Existing", slug="existing")
    db_session.add(filled)
    await db_session.flush()
    p1 = ProjectDB(name="p1", is_billable=True, is_absence=False, status="live", program_id=prog.id)
    p2 = ProjectDB(
        name="p2",
        is_billable=True,
        is_absence=False,
        status="live",
        program_id=prog.id,
        client_id=filled.id,
    )
    db_session.add_all([p1, p2])
    await db_session.flush()
    batch = uuid4()
    row = await _stage(db_session, batch, name="GFW", main_partner="World Resources Institute")
    await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, action=MatchAction.LINK, program_id=prog.id)],
        user_id=None,
    )
    await db_session.refresh(p1)
    await db_session.refresh(p2)
    assert p1.client_id == client.id  # was NULL -> filled
    assert p2.client_id == filled.id  # curated link untouched


@pytest.mark.asyncio
async def test_reapply_is_idempotent_on_terms(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, name="Idem", impact_area_raw="Nature")
    d = [DecisionInput(staging_id=row.id, action=MatchAction.CREATE)]
    await apply_decisions(db_session, batch, d, user_id=None)
    prog = (
        await db_session.execute(select(ProgramDB).where(ProgramDB.name == "Idem"))
    ).scalar_one()
    # Re-apply as LINK to the same program
    await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, action=MatchAction.LINK, program_id=prog.id)],
        user_id=None,
    )
    count = (
        await db_session.execute(
            select(func.count()).select_from(EntityTermDB).where(EntityTermDB.program_id == prog.id)
        )
    ).scalar_one()
    assert count == 1  # not duplicated
