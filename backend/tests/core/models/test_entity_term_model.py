"""Model tests for EntityTermDB — the dual-anchor (project XOR program) tag association."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB


async def _taxonomy_with_term(db: AsyncSession) -> tuple[TaxonomyDB, TaxonomyTermDB]:
    tax = TaxonomyDB(slug="service", name="Service", cardinality=Cardinality.MULTI)
    db.add(tax)
    await db.flush()
    term = TaxonomyTermDB(taxonomy_id=tax.id, slug="tools", name="Tools")
    db.add(term)
    await db.flush()
    return tax, term


@pytest.mark.asyncio
async def test_entity_term_project_anchor_roundtrip(db_session: AsyncSession) -> None:
    tax, term = await _taxonomy_with_term(db_session)
    proj = ProjectDB(name="GFW", is_billable=True, is_absence=False, status="live")
    db_session.add(proj)
    await db_session.flush()

    db_session.add(
        EntityTermDB(term_id=term.id, taxonomy_id=tax.id, project_id=proj.id, is_primary=True)
    )
    await db_session.flush()

    got = (
        await db_session.execute(select(EntityTermDB).where(EntityTermDB.project_id == proj.id))
    ).scalar_one()
    assert got.term_id == term.id
    assert got.program_id is None
    assert got.is_primary is True


@pytest.mark.asyncio
async def test_entity_term_program_anchor_roundtrip(db_session: AsyncSession) -> None:
    tax, term = await _taxonomy_with_term(db_session)
    prog = ProgramDB(name="Anchor Program")
    db_session.add(prog)
    await db_session.flush()

    db_session.add(EntityTermDB(term_id=term.id, taxonomy_id=tax.id, program_id=prog.id))
    await db_session.flush()

    got = (
        await db_session.execute(select(EntityTermDB).where(EntityTermDB.program_id == prog.id))
    ).scalar_one()
    assert got.project_id is None
    assert got.is_primary is False


@pytest.mark.asyncio
async def test_entity_term_rejects_both_anchors_null(db_session: AsyncSession) -> None:
    tax, term = await _taxonomy_with_term(db_session)
    db_session.add(EntityTermDB(term_id=term.id, taxonomy_id=tax.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_entity_term_rejects_both_anchors_set(db_session: AsyncSession) -> None:
    tax, term = await _taxonomy_with_term(db_session)
    proj = ProjectDB(name="Dual", is_billable=True, is_absence=False, status="live")
    prog = ProgramDB(name="Dual Program")
    db_session.add_all([proj, prog])
    await db_session.flush()

    db_session.add(
        EntityTermDB(term_id=term.id, taxonomy_id=tax.id, project_id=proj.id, program_id=prog.id)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
