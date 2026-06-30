import pytest
from sqlalchemy import select

from app.core.models.taxonomy import Cardinality, TaxonomyDB, TaxonomyTermDB


@pytest.mark.asyncio
async def test_create_taxonomy_with_terms(db_session):
    tax = TaxonomyDB(
        slug="impact-area",
        name="Impact Area",
        cardinality=Cardinality.MULTI,
        allows_primary=True,
    )
    db_session.add(tax)
    await db_session.flush()
    db_session.add(TaxonomyTermDB(taxonomy_id=tax.id, slug="nature", name="Nature"))
    await db_session.flush()
    result = await db_session.execute(
        select(TaxonomyTermDB).where(TaxonomyTermDB.taxonomy_id == tax.id)
    )
    terms = result.scalars().all()
    assert len(terms) == 1
    assert terms[0].name == "Nature"
    assert tax.cardinality == Cardinality.MULTI
