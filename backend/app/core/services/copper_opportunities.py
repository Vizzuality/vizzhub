"""Copper opportunities offered for import in the new-project form.

Two groups: open deals in "Happy to Proceed" (pending signature) and deals
that reached "Contract Signed" in the last months without a VizzHub project.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services.copper_client import (
    OPPORTUNITY_STATUS_OPEN,
    OPPORTUNITY_STATUS_WON,
    CopperError,
)
from app.core.services.copper_client_linking import name_key
from app.core.services.name_matching import rank

PENDING_STAGE = "Happy to Proceed"
SIGNED_STAGE = "Contract Signed"
SIGNED_LOOKBACK = timedelta(days=180)

FIELD_CONTRACT_CODE = "Unique Contract Code"
FIELD_CLIENT_CODE = "Client Short Code"
FIELD_START = "Estimated Project Start Date"
FIELD_END = "Estimate Project End"

# Projects predate ISO codes for the two main currencies.
_CURRENCIES = {"USD": "dollar", "EUR": "euro", "GBP": "GBP", "CAD": "CAD"}
# Copper-era codes end in ".<opportunity id>"; old Copper ids have only 6 digits.
_TRAILING_ID = re.compile(r"\.\s*(\d{6,})\s*$")
_SUGGESTION_THRESHOLD = 0.6

Group = Literal["pending_signature", "signed"]


class CopperReader(Protocol):
    async def list_pipeline_stages(self) -> list[dict]: ...
    async def list_custom_field_definitions(self) -> list[dict]: ...
    async def search_opportunities(
        self,
        *,
        pipeline_stage_ids: list[int],
        status_ids: list[int],
        minimum_stage_change_date: int | None = None,
    ) -> list[dict]: ...


class _ProjectRow(Protocol):
    id: UUID
    name: str
    code: str | None
    copper_opportunity_id: int | None


@dataclass(frozen=True)
class ProjectRef:
    id: UUID
    name: str


@dataclass(frozen=True)
class NewClient:
    name: str
    code: str | None
    copper_company_id: int | None


@dataclass
class ImportableOpportunity:
    opportunity_id: int
    name: str
    group: Group
    stage_changed_on: date | None
    company_name: str | None
    code: str | None
    currency: str | None
    original_budget: float | None
    start_date: date | None
    end_date: date | None
    client_id: UUID | None = None
    client_name: str | None = None
    new_client: NewClient | None = None
    linked_projects: list[ProjectRef] = field(default_factory=list)
    suggestion: ProjectRef | None = None


async def list_importable_opportunities(
    db: AsyncSession, copper: CopperReader, *, now: datetime
) -> list[ImportableOpportunity]:
    stages = {s["name"]: s["id"] for s in await copper.list_pipeline_stages()}
    if PENDING_STAGE not in stages or SIGNED_STAGE not in stages:
        raise CopperError("Copper pipeline stages for project import not found")
    fields = {f["name"]: f["id"] for f in await copper.list_custom_field_definitions()}

    pending = await copper.search_opportunities(
        pipeline_stage_ids=[stages[PENDING_STAGE]], status_ids=[OPPORTUNITY_STATUS_OPEN]
    )
    signed = await copper.search_opportunities(
        pipeline_stage_ids=[stages[SIGNED_STAGE]],
        status_ids=[OPPORTUNITY_STATUS_WON],
        minimum_stage_change_date=int((now - SIGNED_LOOKBACK).timestamp()),
    )

    projects = await _ProjectIndex.load(db)
    clients = await _ClientIndex.load(db)
    result = [_build(o, "pending_signature", fields, projects, clients) for o in pending]
    result += [
        opp
        for opp in (_build(o, "signed", fields, projects, clients) for o in signed)
        if not opp.linked_projects
    ]
    result.sort(key=lambda o: (o.group != "pending_signature", -_ordinal(o.stage_changed_on)))
    return result


def _ordinal(day: date | None) -> int:
    return day.toordinal() if day else 0


def _build(
    raw: dict,
    group: Group,
    fields: dict[str, int],
    projects: "_ProjectIndex",
    clients: "_ClientIndex",
) -> ImportableOpportunity:
    custom = {
        c["custom_field_definition_id"]: c.get("value") for c in raw.get("custom_fields") or []
    }

    def text(name: str) -> str | None:
        value = custom.get(fields.get(name, -1))
        return (value.strip() or None) if isinstance(value, str) else None

    def day(name: str) -> date | None:
        value = custom.get(fields.get(name, -1))
        return _to_date(value) if isinstance(value, int) else None

    linked = projects.linked_to(raw["id"])
    code = text(FIELD_CONTRACT_CODE)
    opp = ImportableOpportunity(
        opportunity_id=raw["id"],
        name=raw["name"],
        group=group,
        stage_changed_on=_to_date(raw.get("date_stage_changed")),
        company_name=raw.get("company_name"),
        code=code,
        currency=_CURRENCIES.get((raw.get("monetary_unit") or "").upper()),
        original_budget=raw.get("monetary_value"),
        start_date=day(FIELD_START),
        end_date=day(FIELD_END),
        linked_projects=linked,
        suggestion=None if linked else projects.suggest(raw["name"], code),
    )
    clients.resolve(opp, raw.get("company_id"), text(FIELD_CLIENT_CODE))
    return opp


def _to_date(timestamp: object) -> date | None:
    if not isinstance(timestamp, int) or timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, UTC).date()


class _ProjectIndex:
    def __init__(self, rows: list[_ProjectRow]) -> None:
        self._by_opportunity: dict[int, list[ProjectRef]] = {}
        self._names: list[tuple[str, ProjectRef]] = []
        for project in rows:
            ref = ProjectRef(id=project.id, name=project.name)
            self._names.append((project.name, ref))
            for opp_id in _opportunity_ids(project):
                self._by_opportunity.setdefault(opp_id, []).append(ref)

    @classmethod
    async def load(cls, db: AsyncSession) -> "_ProjectIndex":
        stmt = select(ProjectDB.id, ProjectDB.name, ProjectDB.code, ProjectDB.copper_opportunity_id)
        rows = (await db.execute(stmt)).all()
        return cls(list(rows))

    def linked_to(self, opportunity_id: int) -> list[ProjectRef]:
        return list(self._by_opportunity.get(opportunity_id, []))

    def suggest(self, name: str, code: str | None) -> ProjectRef | None:
        """Extensions often reuse the parent contract's code; else fall back to the name."""
        match = _TRAILING_ID.search(code or "")
        parent = self._by_opportunity.get(int(match.group(1)), []) if match else []
        if parent:
            return parent[0]
        best = rank(name, self._names, limit=1, threshold=_SUGGESTION_THRESHOLD)
        return cast(ProjectRef, best[0].payload) if best else None


def _opportunity_ids(project: _ProjectRow) -> set[int]:
    """An explicit link, plus the opportunity id that ends most Copper-era codes."""
    ids = {project.copper_opportunity_id} if project.copper_opportunity_id else set()
    match = _TRAILING_ID.search(project.code or "")
    if match:
        ids.add(int(match.group(1)))
    return ids


class _ClientIndex:
    def __init__(self, rows: list[ClientDB]) -> None:
        self._by_company = {c.copper_company_id: c for c in rows if c.copper_company_id}
        self._codes = {c.code for c in rows if c.code}
        by_name: dict[str, list[ClientDB]] = {}
        for client in rows:
            by_name.setdefault(name_key(client.name), []).append(client)
        self._by_name = by_name

    @classmethod
    async def load(cls, db: AsyncSession) -> "_ClientIndex":
        stmt = select(ClientDB).where(ClientDB.is_active.is_(True))
        rows = (await db.execute(stmt)).scalars().all()
        return cls(list(rows))

    def resolve(
        self, opp: ImportableOpportunity, company_id: int | None, client_code: str | None
    ) -> None:
        if not opp.company_name:
            return
        client = self._by_company.get(company_id) if company_id else None
        if client is None:
            # A same-name client already linked to another Copper company is a namesake.
            same_name = [
                c
                for c in self._by_name.get(name_key(opp.company_name), [])
                if c.copper_company_id in (None, company_id)
            ]
            client = same_name[0] if len(same_name) == 1 else None
        if client is not None:
            opp.client_id, opp.client_name = client.id, client.name
            return
        free_code = client_code if client_code not in self._codes else None
        opp.new_client = NewClient(
            name=opp.company_name, code=free_code, copper_company_id=company_id
        )
