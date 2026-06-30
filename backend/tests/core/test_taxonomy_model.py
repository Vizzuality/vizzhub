import pytest
from sqlalchemy import select, text

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

    # The ORM must serialize the enum by VALUE (lowercase), matching the labels the
    # Alembic migration creates ('single'/'multi') — NOT the member name ('MULTI').
    # Guards against the StrEnum/native-enum drift where create_all (name-based) and
    # the migration (value-based) disagree and inserts fail against the real DB.
    raw = await db_session.execute(
        text("SELECT cardinality::text FROM taxonomies WHERE id = :id"), {"id": tax.id}
    )
    assert raw.scalar_one() == "multi"
