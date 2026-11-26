"""Linking VizzHub clients to Copper companies by exact (normalized) name."""

from datetime import date

import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services.copper_client_linking import link_clients_to_copper


async def _client(db, name: str, slug: str, **kw) -> ClientDB:
    client = ClientDB(name=name, slug=slug, **kw)
    db.add(client)
    await db.flush()
    return client


def _review(report, client: ClientDB) -> dict:
    return next(item for item in report.review if item.client_id == client.id)


@pytest.mark.asyncio
async def test_links_unique_match_ignoring_case_and_accents(db_session):
    client = await _client(db_session, "Fundación Biodiversidad", "fb")

    report = await link_clients_to_copper(
        db_session, [{"id": 11, "name": "FUNDACION  BIODIVERSIDAD"}]
    )

    await db_session.refresh(client)
    assert client.copper_company_id == 11
    assert report.linked == 1
    assert report.review == []


@pytest.mark.asyncio
async def test_already_linked_clients_and_companies_are_left_alone(db_session):
    linked = await _client(db_session, "Mongabay", "mongabay", copper_company_id=5)
    other = await _client(db_session, "Mongabay", "mongabay-2")

    report = await link_clients_to_copper(db_session, [{"id": 5, "name": "Mongabay"}])

    await db_session.refresh(linked)
    await db_session.refresh(other)
    assert linked.copper_company_id == 5
    assert other.copper_company_id is None
    assert report.linked == 0
    assert report.already_linked == 1
    assert _review(report, other).reason == "duplicate_in_vizzhub"


@pytest.mark.asyncio
async def test_several_copper_companies_with_the_name_go_to_review(db_session):
    client = await _client(db_session, "WWF", "wwf")

    report = await link_clients_to_copper(
        db_session,
        [
            {
                "id": 1,
                "name": "WWF",
                "email_domain": "wwf.org",
                "date_created": 1577750400,
                "interaction_count": 39,
            },
            {"id": 2, "name": "wwf"},
        ],
    )

    await db_session.refresh(client)
    assert client.copper_company_id is None
    item = _review(report, client)
    assert item.reason == "ambiguous_in_copper"
    first, second = sorted(item.candidates, key=lambda c: c.id)
    assert (first.id, first.email_domain, first.created_on, first.interaction_count) == (
        1,
        "wwf.org",
        date(2019, 12, 31),
        39,
    )
    assert (second.email_domain, second.created_on, second.interaction_count) == (None, None, 0)


@pytest.mark.asyncio
async def test_duplicate_vizzhub_clients_link_the_one_with_projects(db_session):
    empty = await _client(db_session, "World Bank Group", "wbg-empty")
    used = await _client(db_session, "World Bank Group", "wbg-used")
    db_session.add(ProjectDB(name="WB Maps", client_id=used.id))
    await db_session.flush()

    report = await link_clients_to_copper(db_session, [{"id": 649763, "name": "World Bank Group"}])

    await db_session.refresh(empty)
    await db_session.refresh(used)
    assert used.copper_company_id == 649763
    assert empty.copper_company_id is None
    item = _review(report, empty)
    assert item.reason == "duplicate_in_vizzhub"
    assert [c.id for c in item.candidates] == [649763]


@pytest.mark.asyncio
async def test_client_missing_from_copper_goes_to_review(db_session):
    client = await _client(db_session, "Wwfint", "wwfint")

    report = await link_clients_to_copper(db_session, [{"id": 1, "name": "WWF International"}])

    item = _review(report, client)
    assert item.reason == "not_in_copper"
    assert item.candidates == []


@pytest.mark.asyncio
async def test_second_run_is_a_no_op(db_session):
    await _client(db_session, "Systemiq", "systemiq")
    companies = [{"id": 77916335, "name": "Systemiq"}]

    first = await link_clients_to_copper(db_session, companies)
    second = await link_clients_to_copper(db_session, companies)

    assert (first.linked, second.linked, second.already_linked) == (1, 0, 1)


@pytest.mark.asyncio
async def test_exact_spelling_breaks_ties_between_same_name_pairs(db_session):
    lower = await _client(db_session, "aidenvironment", "aid-lower")
    camel = await _client(db_session, "AidEnvironment", "aid-camel")

    report = await link_clients_to_copper(
        db_session, [{"id": 1, "name": "aidenvironment"}, {"id": 2, "name": "AidEnvironment"}]
    )

    await db_session.refresh(lower)
    await db_session.refresh(camel)
    assert (lower.copper_company_id, camel.copper_company_id) == (1, 2)
    assert report.review == []


@pytest.mark.asyncio
async def test_identical_pairs_stay_in_review(db_session):
    first = await _client(db_session, "Verra", "verra-1")
    await _client(db_session, "Verra", "verra-2")

    report = await link_clients_to_copper(
        db_session, [{"id": 1, "name": "Verra"}, {"id": 2, "name": "Verra"}]
    )

    await db_session.refresh(first)
    assert first.copper_company_id is None
    assert len(report.review) == 2


@pytest.mark.asyncio
async def test_names_match_ignoring_spaces(db_session):
    client = await _client(db_session, "Sky Truth", "sky-truth")

    report = await link_clients_to_copper(db_session, [{"id": 2801827, "name": "SkyTruth"}])

    await db_session.refresh(client)
    assert client.copper_company_id == 2801827
    assert report.linked == 1


@pytest.mark.asyncio
async def test_spacing_variant_of_a_linked_client_is_a_duplicate(db_session):
    await _client(db_session, "SkyTruth", "skytruth", copper_company_id=2801827)
    variant = await _client(db_session, "Sky Truth", "sky-truth")

    report = await link_clients_to_copper(db_session, [{"id": 2801827, "name": "SkyTruth"}])

    assert _review(report, variant).reason == "duplicate_in_vizzhub"
