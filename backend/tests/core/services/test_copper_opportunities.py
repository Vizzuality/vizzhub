"""Opportunities offered for import into the new-project form."""

from datetime import UTC, date, datetime

import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services.copper_client import OPPORTUNITY_STATUS_OPEN, OPPORTUNITY_STATUS_WON
from app.core.services.copper_opportunities import list_importable_opportunities

HTP, SIGNED = 124540, 124566
NOW = datetime(2026, 11, 25, tzinfo=UTC)
FIELDS = [
    {"id": 670459, "name": "Unique Contract Code", "data_type": "String"},
    {"id": 670447, "name": "Client Short Code", "data_type": "String"},
    {"id": 9263, "name": "Estimated Project Start Date", "data_type": "Date"},
    {"id": 9310, "name": "Estimate Project End", "data_type": "Date"},
]


def _opp(opp_id: int, name: str, *, company_id: int | None, company: str, **fields) -> dict:
    custom = {
        670459: fields.get("code"),
        670447: fields.get("client_code"),
        9263: fields.get("start"),
        9310: fields.get("end"),
    }
    return {
        "id": opp_id,
        "name": name,
        "company_id": company_id,
        "company_name": company,
        "monetary_value": fields.get("value"),
        "monetary_unit": fields.get("unit"),
        "date_stage_changed": fields.get("changed", 1795392000),
        "custom_fields": [{"custom_field_definition_id": k, "value": v} for k, v in custom.items()],
    }


class FakeCopper:
    def __init__(self, pending: list[dict], signed: list[dict] | None = None) -> None:
        self.pending, self.signed = pending, signed or []
        self.calls: list[dict] = []

    async def list_pipeline_stages(self) -> list[dict]:
        return [
            {"id": HTP, "name": "Happy to Proceed", "pipeline_id": 1},
            {"id": SIGNED, "name": "Contract Signed", "pipeline_id": 1},
        ]

    async def list_custom_field_definitions(self) -> list[dict]:
        return FIELDS

    async def search_opportunities(self, **filters) -> list[dict]:
        self.calls.append(filters)
        return self.pending if filters["pipeline_stage_ids"] == [HTP] else self.signed


WRIP = _opp(
    39491052,
    "WRIP Design",
    company_id=77916335,
    company="Systemiq.earth",
    code="Sys.WRIP.39491052",
    client_code="Sys",
    value=48040.0,
    unit="EUR",
    start=1795996800,
    end=1798675200,
)


@pytest.mark.asyncio
async def test_pending_opportunity_prefills_the_project(db_session):
    client = ClientDB(name="Systemiq", slug="systemiq", copper_company_id=77916335)
    db_session.add(client)
    await db_session.flush()

    [opp] = await list_importable_opportunities(db_session, FakeCopper([WRIP]), now=NOW)

    assert (opp.opportunity_id, opp.group, opp.name, opp.code) == (
        39491052,
        "pending_signature",
        "WRIP Design",
        "Sys.WRIP.39491052",
    )
    assert (opp.currency, opp.original_budget) == ("euro", 48040.0)
    assert (opp.start_date, opp.end_date) == (date(2026, 11, 30), date(2026, 12, 31))
    assert (opp.client_id, opp.new_client) == (client.id, None)
    assert opp.linked_projects == []


@pytest.mark.asyncio
async def test_searches_open_pending_and_recent_open_or_won_signed(db_session):
    copper = FakeCopper([])

    await list_importable_opportunities(db_session, copper, now=NOW)

    pending, signed = copper.calls
    assert pending["pipeline_stage_ids"] == [HTP]
    assert pending["status_ids"] == [OPPORTUNITY_STATUS_OPEN]
    assert signed["pipeline_stage_ids"] == [SIGNED]
    # Moving a deal to Contract Signed does not mark it Won in Copper.
    assert signed["status_ids"] == [OPPORTUNITY_STATUS_OPEN, OPPORTUNITY_STATUS_WON]
    assert signed["minimum_stage_change_date"] == int(datetime(2026, 5, 29, tzinfo=UTC).timestamp())


@pytest.mark.asyncio
async def test_unlinked_client_is_matched_by_name_else_proposed_new(db_session):
    by_name = ClientDB(name="World Bank Group", slug="wbg")
    db_session.add(by_name)
    await db_session.flush()
    wb = _opp(1, "WB Design", company_id=649763, company="World Bank Group", client_code="WBG")
    csu = _opp(
        2,
        "Colorado Forest Atlas",
        company_id=77041056,
        company="Colorado State University",
        client_code="CSFS",
    )

    result = await list_importable_opportunities(db_session, FakeCopper([wb, csu]), now=NOW)

    by_id = {o.opportunity_id: o for o in result}
    assert by_id[1].client_id == by_name.id
    assert by_id[2].client_id is None
    new = by_id[2].new_client
    assert (new.name, new.code, new.copper_company_id) == (
        "Colorado State University",
        "CSFS",
        77041056,
    )


@pytest.mark.asyncio
async def test_projects_link_by_id_or_by_code_suffix(db_session):
    db_session.add_all(
        [
            ProjectDB(name="WRIP", copper_opportunity_id=39491052),
            ProjectDB(name="WB One Geospatial", code="WBG.WBOGPD.39153406"),
        ]
    )
    await db_session.flush()
    wb = _opp(39153406, "World Bank One Geospatial", company_id=None, company="World Bank Group")

    result = await list_importable_opportunities(db_session, FakeCopper([WRIP, wb]), now=NOW)

    names = {o.opportunity_id: [p.name for p in o.linked_projects] for o in result}
    assert names == {39491052: ["WRIP"], 39153406: ["WB One Geospatial"]}


@pytest.mark.asyncio
async def test_signed_opportunities_already_in_vizzhub_are_hidden(db_session):
    db_session.add(ProjectDB(name="GMW Phase 9", code="TNC.GMW.33647500"))
    await db_session.flush()
    done = _opp(33647500, "GMW updates", company_id=None, company="TNC")
    todo = _opp(39133412, "Rangelands 2026 extension", company_id=None, company="GMV")

    result = await list_importable_opportunities(
        db_session, FakeCopper([], signed=[done, todo]), now=NOW
    )

    assert [(o.opportunity_id, o.group) for o in result] == [(39133412, "signed")]


@pytest.mark.asyncio
async def test_unlinked_opportunity_suggests_a_similar_project(db_session):
    project = ProjectDB(name="Rangelands extension 2026")
    db_session.add(project)
    await db_session.flush()
    opp = _opp(39133412, "Rangelands 2026 extension", company_id=None, company="GMV")

    [result] = await list_importable_opportunities(db_session, FakeCopper([opp]), now=NOW)

    assert result.suggestion is not None
    assert result.suggestion.id == project.id


@pytest.mark.asyncio
async def test_same_name_client_linked_to_another_company_is_not_reused(db_session):
    db_session.add(ClientDB(name="WWF", slug="wwf-us", copper_company_id=1))
    await db_session.flush()
    opp = _opp(5, "Rivers", company_id=2, company="WWF", client_code="WWF")

    [result] = await list_importable_opportunities(db_session, FakeCopper([opp]), now=NOW)

    assert result.client_id is None
    assert result.new_client.copper_company_id == 2


@pytest.mark.asyncio
async def test_new_client_drops_a_code_another_client_uses(db_session):
    db_session.add(ClientDB(name="The Water Institute", slug="twi", code="WI"))
    await db_session.flush()
    opp = _opp(
        6, "Wetlands Atlas", company_id=9, company="Wetlands International", client_code="WI"
    )

    [result] = await list_importable_opportunities(db_session, FakeCopper([opp]), now=NOW)

    assert (result.new_client.name, result.new_client.code) == ("Wetlands International", None)


@pytest.mark.asyncio
async def test_extension_code_pointing_at_a_parent_contract_suggests_that_project(db_session):
    parent = ProjectDB(name="Global Mangrove Watch Phase 9", code="TNC.GMW.33647500")
    db_session.add_all([parent, ProjectDB(name="Global Mangrove Watch 3", code="TNC.GMW3")])
    await db_session.flush()
    ext = _opp(
        39000001,
        "Global Mangrove Watch updates 2026",
        company_id=None,
        company="TNC",
        code="TNC .GMW2026.TNC.GMW.33647500",
    )

    [result] = await list_importable_opportunities(db_session, FakeCopper([ext]), now=NOW)

    assert result.linked_projects == []
    assert result.suggestion.id == parent.id


@pytest.mark.asyncio
async def test_only_a_dot_separated_trailing_number_counts_as_an_opportunity_id(db_session):
    db_session.add(ProjectDB(name="Report 2024", code="RPT202405"))
    await db_session.flush()
    opp = _opp(202405, "Something else", company_id=None, company="X")

    [result] = await list_importable_opportunities(db_session, FakeCopper([opp]), now=NOW)

    assert result.linked_projects == []


@pytest.mark.asyncio
async def test_several_projects_on_the_parent_contract_suggest_the_latest(db_session):
    phase8 = ProjectDB(
        name="Global Mangrove Watch Phase 8", code="TNC.GMW.33647500", start_date=date(2025, 6, 1)
    )
    phase9 = ProjectDB(
        name="Global Mangrove Watch Phase 9", code="TNC.GMW.33647500", start_date=date(2026, 11, 2)
    )
    db_session.add_all([phase8, phase9])
    await db_session.flush()
    ext = _opp(
        39000002,
        "Global Mangrove Watch updates 2026",
        company_id=None,
        company="TNC",
        code="TNC .GMW2026.TNC.GMW.33647500",
    )

    [result] = await list_importable_opportunities(db_session, FakeCopper([ext]), now=NOW)

    assert result.suggestion.id == phase9.id
