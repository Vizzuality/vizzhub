"""Replays migration 096's SQL against the test schema (create_all == prod shape)."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB

MIGRATION = Path(__file__).parents[2] / "alembic" / "versions" / "096_portfolio_program_rollup.py"


def _statements() -> list[str]:
    spec = importlib.util.spec_from_file_location("mig096", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.ROLLUP_STATEMENTS


async def _run_rollup(db: AsyncSession) -> None:
    for stmt in _statements():
        await db.execute(text(stmt))


async def _program_with_project(db: AsyncSession, *, prog_name: str, proj_name: str):
    prog = ProgramDB(name=prog_name)
    db.add(prog)
    await db.flush()
    proj = ProjectDB(
        name=proj_name, is_billable=True, is_absence=False, status="live", program_id=prog.id
    )
    db.add(proj)
    await db.flush()
    return prog, proj


@pytest.mark.asyncio
async def test_promotes_project_profile_to_profileless_program(db_session: AsyncSession) -> None:
    prog, proj = await _program_with_project(db_session, prog_name="P1", proj_name="P1 iter")
    db_session.add(PortfolioProfileDB(project_id=proj.id, objective="obj", stage="live"))
    await db_session.flush()

    await _run_rollup(db_session)

    rows = (await db_session.execute(select(PortfolioProfileDB))).scalars().all()
    assert len(rows) == 1
    assert rows[0].program_id == prog.id
    assert rows[0].project_id is None
    assert rows[0].objective == "obj"


@pytest.mark.asyncio
async def test_collision_program_profile_wins_field_by_field(db_session: AsyncSession) -> None:
    prog, proj = await _program_with_project(db_session, prog_name="P2", proj_name="P2 iter")
    db_session.add(
        PortfolioProfileDB(program_id=prog.id, objective="program-obj", short_description=None)
    )
    db_session.add(
        PortfolioProfileDB(project_id=proj.id, objective="proj-obj", short_description="proj-desc")
    )
    await db_session.flush()

    await _run_rollup(db_session)

    rows = (await db_session.execute(select(PortfolioProfileDB))).scalars().all()
    assert len(rows) == 1
    assert rows[0].program_id == prog.id
    assert rows[0].objective == "program-obj"  # program value kept
    assert rows[0].short_description == "proj-desc"  # null filled from project


@pytest.mark.asyncio
async def test_terms_reanchor_and_dedupe(db_session: AsyncSession) -> None:
    prog, proj = await _program_with_project(db_session, prog_name="P3", proj_name="P3 iter")
    tax = TaxonomyDB(slug="service", name="Service", cardinality=Cardinality.MULTI)
    db_session.add(tax)
    await db_session.flush()
    t1 = TaxonomyTermDB(taxonomy_id=tax.id, slug="tools", name="Tools")
    t2 = TaxonomyTermDB(taxonomy_id=tax.id, slug="strategic", name="Strategic")
    db_session.add_all([t1, t2])
    await db_session.flush()
    # t1 already on the program AND on the project (duplicate) — t2 only on the project.
    db_session.add(EntityTermDB(term_id=t1.id, taxonomy_id=tax.id, program_id=prog.id))
    db_session.add(EntityTermDB(term_id=t1.id, taxonomy_id=tax.id, project_id=proj.id))
    db_session.add(EntityTermDB(term_id=t2.id, taxonomy_id=tax.id, project_id=proj.id))
    await db_session.flush()

    await _run_rollup(db_session)

    rows = (await db_session.execute(select(EntityTermDB))).scalars().all()
    assert all(r.program_id == prog.id and r.project_id is None for r in rows)
    assert sorted(str(r.term_id) for r in rows) == sorted([str(t1.id), str(t2.id)])


@pytest.mark.asyncio
async def test_second_primary_demoted_on_rollup(db_session: AsyncSession) -> None:
    prog, proj = await _program_with_project(db_session, prog_name="P4", proj_name="P4 iter")
    tax = TaxonomyDB(
        slug="impact-area", name="Impact Area", cardinality=Cardinality.MULTI, allows_primary=True
    )
    db_session.add(tax)
    await db_session.flush()
    t1 = TaxonomyTermDB(taxonomy_id=tax.id, slug="nature", name="Nature")
    t2 = TaxonomyTermDB(taxonomy_id=tax.id, slug="climate", name="Climate")
    db_session.add_all([t1, t2])
    await db_session.flush()
    early = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.add(
        EntityTermDB(
            term_id=t1.id,
            taxonomy_id=tax.id,
            program_id=prog.id,
            is_primary=True,
            assigned_at=early,
        )
    )
    db_session.add(
        EntityTermDB(
            term_id=t2.id,
            taxonomy_id=tax.id,
            project_id=proj.id,
            is_primary=True,
            assigned_at=early + timedelta(days=1),
        )
    )
    await db_session.flush()

    await _run_rollup(db_session)

    rows = (await db_session.execute(select(EntityTermDB))).scalars().all()
    primaries = [r for r in rows if r.is_primary]
    assert len(primaries) == 1
    assert primaries[0].term_id == t1.id  # program's pre-existing primary kept
