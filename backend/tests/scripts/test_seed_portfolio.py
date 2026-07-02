import pytest
from sqlalchemy import select

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import TaxonomyDB
from app.scripts.seed_portfolio import link_projects_by_code, seed_taxonomies


@pytest.mark.asyncio
async def test_seed_taxonomies_idempotent(db_session):
    created_first = await seed_taxonomies(db_session)
    await db_session.flush()
    created_second = await seed_taxonomies(db_session)
    assert created_first > 0
    assert created_second == 0  # nothing new on second run
    impact = (
        await db_session.execute(select(TaxonomyDB).where(TaxonomyDB.slug == "impact-area"))
    ).scalar_one()
    assert impact.allows_primary is True


@pytest.mark.asyncio
async def test_link_projects_by_code(db_session):
    matched = ClientDB(name="Acme Foundation", slug="acme-foundation", code="ACME")
    other = ClientDB(name="Beta Org", slug="beta-org", code="BETA")
    db_session.add_all([matched, other])
    await db_session.flush()

    # Prefix matches a client code -> linked.
    p_match = ProjectDB(name="Acme site", code="ACME.SITE.24")
    # Prefix has no matching client code -> untouched.
    p_unmatched = ProjectDB(name="Orphan", code="ZZZ.NONE")
    # Already linked -> never overwritten.
    p_prelinked = ProjectDB(name="Beta thing", code="ACME.OTHER", client_id=other.id)
    # No code at all -> untouched.
    p_nocode = ProjectDB(name="Codeless", code=None)
    db_session.add_all([p_match, p_unmatched, p_prelinked, p_nocode])
    await db_session.flush()

    linked = await link_projects_by_code(db_session)
    await db_session.flush()

    assert linked == 1
    await db_session.refresh(p_match)
    await db_session.refresh(p_unmatched)
    await db_session.refresh(p_prelinked)
    assert p_match.client_id == matched.id
    assert p_unmatched.client_id is None
    assert p_prelinked.client_id == other.id  # not overwritten

    # Idempotent: second run links nothing new.
    linked_again = await link_projects_by_code(db_session)
    assert linked_again == 0
