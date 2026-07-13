"""Tests for Portfolio command handler."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.models.user import UserDB
from mcp_server.handlers.portfolio import execute


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(email="portfolio-test@vizzuality.com", name="Portfolio Tester")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def catalogue(db_session: AsyncSession, test_user: UserDB) -> dict:
    """One program with profile, one taxonomy with two terms (one assigned)."""
    program = ProgramDB(name="Alpha Program")
    db_session.add(program)
    await db_session.flush()
    db_session.add(
        PortfolioProfileDB(
            program_id=program.id,
            stage="live",
            objective="Original objective",
            main_partner="Original partner",
        )
    )
    tax = TaxonomyDB(
        slug="geography", name="Geography", cardinality=Cardinality.MULTI, allows_primary=True
    )
    db_session.add(tax)
    await db_session.flush()
    europe = TaxonomyTermDB(taxonomy_id=tax.id, slug="europe", name="Europe")
    africa = TaxonomyTermDB(taxonomy_id=tax.id, slug="africa", name="Africa")
    db_session.add_all([europe, africa])
    await db_session.flush()
    db_session.add(
        EntityTermDB(term_id=europe.id, taxonomy_id=tax.id, program_id=program.id)
    )
    await db_session.flush()
    return {"program": program, "taxonomy": tax, "europe": europe, "africa": africa}


@pytest.mark.asyncio
async def test_create_program(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    result = await execute("create_program", None, {"name": "Beta Program"}, test_user.id, db_session)
    assert result["name"] == "Beta Program"
    created = (
        await db_session.execute(select(ProgramDB).where(ProgramDB.name == "Beta Program"))
    ).scalar_one()
    assert str(created.id) == result["program_id"]


@pytest.mark.asyncio
async def test_create_program_duplicate_name_rejected(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    with pytest.raises(ValueError, match="already exists"):
        await execute("create_program", None, {"name": "alpha program"}, test_user.id, db_session)


@pytest.mark.asyncio
async def test_rename_program(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    program = catalogue["program"]
    result = await execute(
        "rename_program", str(program.id), {"name": "Alpha Renamed"}, test_user.id, db_session
    )
    assert result["name"] == "Alpha Renamed"
    await db_session.refresh(program)
    assert program.name == "Alpha Renamed"


@pytest.mark.asyncio
async def test_update_profile_patches_and_clears(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    program = catalogue["program"]
    result = await execute(
        "update_profile",
        str(program.id),
        {"objective": "New objective", "main_partner": ""},
        test_user.id,
        db_session,
    )
    profile = result["profile"]
    assert profile["objective"] == "New objective"
    assert profile["main_partner"] is None  # empty string clears
    assert profile["stage"] == "live"  # untouched field preserved


@pytest.mark.asyncio
async def test_update_profile_unknown_program(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    with pytest.raises(ValueError, match="not found"):
        await execute(
            "update_profile",
            "00000000-0000-0000-0000-000000000001",
            {"objective": "x"},
            test_user.id,
            db_session,
        )


@pytest.mark.asyncio
async def test_set_tags_replaces_terms_with_primary(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    program = catalogue["program"]
    result = await execute(
        "set_tags",
        str(program.id),
        {"taxonomy": "Geography", "term_names": ["africa"], "primary": "Africa"},
        test_user.id,
        db_session,
    )
    assert [t["name"] for t in result["terms"]] == ["Africa"]
    assert result["terms"][0]["is_primary"] is True
    rows = (
        (
            await db_session.execute(
                select(EntityTermDB).where(EntityTermDB.program_id == program.id)
            )
        )
        .scalars()
        .all()
    )
    # Europe was replaced, only Africa remains
    assert [r.term_id for r in rows] == [catalogue["africa"].id]


@pytest.mark.asyncio
async def test_set_tags_unknown_term_rejected(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    program = catalogue["program"]
    with pytest.raises(ValueError, match="Terms not found"):
        await execute(
            "set_tags",
            str(program.id),
            {"taxonomy": "geography", "term_names": ["Atlantis"]},
            test_user.id,
            db_session,
        )


@pytest.mark.asyncio
async def test_unknown_action_raises(
    db_session: AsyncSession, test_user: UserDB, catalogue: dict
) -> None:
    with pytest.raises(ValueError, match="Unknown portfolio action"):
        await execute("drop_everything", None, {}, test_user.id, db_session)
