from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_overview import (
    PortfolioOverviewStagingDB,
    PortfolioProfileDB,
    ProgramAction,
)
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.services.overview_import import DecisionInput, apply_decisions


async def _seed_taxonomies(db: AsyncSession) -> None:
    impact = TaxonomyDB(
        slug="impact-area", name="Impact area", cardinality="multi", allows_primary=True
    )
    topics = TaxonomyDB(slug="topics", name="Topics", cardinality="multi", allows_primary=False)
    db.add_all([impact, topics])
    await db.flush()
    db.add_all(
        [
            TaxonomyTermDB(taxonomy_id=impact.id, slug="nature", name="Nature"),
            TaxonomyTermDB(taxonomy_id=impact.id, slug="climate", name="Climate"),
        ]
    )
    await db.flush()


async def _proj(db, name, **kw) -> ProjectDB:
    p = ProjectDB(name=name, is_billable=True, is_absence=False, status="live", **kw)
    db.add(p)
    await db.flush()
    return p


async def _stage(db, batch, **kw) -> PortfolioOverviewStagingDB:
    row = PortfolioOverviewStagingDB(
        import_batch=batch, row_index=3, name=kw.pop("name", "X"), **kw
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_create_program_and_project_profile_and_terms(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    proj = await _proj(db_session, "Airqast")
    batch = uuid4()
    row = await _stage(
        db_session,
        batch,
        name="Airqast",
        impact_area_raw="Nature, Climate",
        topics_raw="Air quality",
        objective="Clean air",
    )
    result = await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, project_id=proj.id, program_action=ProgramAction.CREATE)],
        user_id=None,
    )
    assert result.programs_created == 1
    await db_session.refresh(proj)
    assert proj.program_id is not None
    profile = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.project_id == proj.id)
        )
    ).scalar_one()
    assert profile.objective == "Clean air"
    n = (
        await db_session.execute(
            select(func.count()).select_from(EntityTermDB).where(EntityTermDB.project_id == proj.id)
        )
    ).scalar_one()
    assert n == 3  # Nature + Climate + Air quality(created); all on the PROJECT


@pytest.mark.asyncio
async def test_inherit_leaves_program(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    prog = ProgramDB(name="Aqueduct")
    db_session.add(prog)
    await db_session.flush()
    proj = await _proj(db_session, "Aqueduct maintenance", program_id=prog.id)
    batch = uuid4()
    row = await _stage(db_session, batch, name="Aqueduct maintenance")
    await apply_decisions(
        db_session,
        batch,
        [
            DecisionInput(
                staging_id=row.id, project_id=proj.id, program_action=ProgramAction.INHERIT
            )
        ],
        user_id=None,
    )
    await db_session.refresh(proj)
    assert proj.program_id == prog.id


@pytest.mark.asyncio
async def test_skip_when_no_project(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    batch = uuid4()
    row = await _stage(db_session, batch, name="Ghost")
    result = await apply_decisions(
        db_session,
        batch,
        [DecisionInput(staging_id=row.id, project_id=None, program_action=ProgramAction.NONE)],
        user_id=None,
    )
    assert result.skipped == 1
    assert result.applied == 0


@pytest.mark.asyncio
async def test_client_cascade_to_program_siblings_only_null(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    client = ClientDB(name="World Resources Institute", slug="world-resources-institute")
    prog = ProgramDB(name="GFW")
    db_session.add_all([client, prog])
    await db_session.flush()
    filled_client = ClientDB(name="Existing", slug="existing")
    db_session.add(filled_client)
    await db_session.flush()
    target = await _proj(db_session, "GFW platform", program_id=prog.id)
    sibling_null = await _proj(db_session, "GFW sib A", program_id=prog.id)
    sibling_set = await _proj(
        db_session, "GFW sib B", program_id=prog.id, client_id=filled_client.id
    )
    batch = uuid4()
    row = await _stage(
        db_session, batch, name="GFW platform", main_partner="World Resources Institute"
    )
    await apply_decisions(
        db_session,
        batch,
        [
            DecisionInput(
                staging_id=row.id, project_id=target.id, program_action=ProgramAction.INHERIT
            )
        ],
        user_id=None,
    )
    for p in (target, sibling_null, sibling_set):
        await db_session.refresh(p)
    assert target.client_id == client.id
    assert sibling_null.client_id == client.id  # NULL sibling filled
    assert sibling_set.client_id == filled_client.id  # curated untouched


@pytest.mark.asyncio
async def test_failing_row_does_not_discard_prior_rows(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    good = await _proj(db_session, "Good One")
    batch = uuid4()
    row_a = await _stage(db_session, batch, name="Good One")
    row_b = await _stage(db_session, batch, name="Bad One")
    result = await apply_decisions(
        db_session,
        batch,
        [
            DecisionInput(
                staging_id=row_a.id, project_id=good.id, program_action=ProgramAction.CREATE
            ),
            # LINK to a non-existent program → _resolve_program raises inside its savepoint
            DecisionInput(
                staging_id=row_b.id,
                project_id=good.id,
                program_action=ProgramAction.LINK,
                program_id=uuid4(),
            ),
        ],
        user_id=None,
    )
    await db_session.refresh(good)
    assert good.program_id is not None  # row A persisted
    assert result.programs_created == 1
    assert result.applied == 1


@pytest.mark.asyncio
async def test_reapply_idempotent_on_terms(db_session: AsyncSession) -> None:
    await _seed_taxonomies(db_session)
    proj = await _proj(db_session, "Idem")
    batch = uuid4()
    row = await _stage(db_session, batch, name="Idem", impact_area_raw="Nature")
    d = [DecisionInput(staging_id=row.id, project_id=proj.id, program_action=ProgramAction.NONE)]
    await apply_decisions(db_session, batch, d, user_id=None)
    await apply_decisions(db_session, batch, d, user_id=None)
    n = (
        await db_session.execute(
            select(func.count()).select_from(EntityTermDB).where(EntityTermDB.project_id == proj.id)
        )
    ).scalar_one()
    assert n == 1
