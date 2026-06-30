import pytest
from sqlalchemy import select

from app.core.models.taxonomy import TaxonomyDB
from app.scripts.seed_portfolio import seed_taxonomies


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
