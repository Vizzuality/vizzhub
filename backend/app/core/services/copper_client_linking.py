"""Link VizzHub clients to Copper companies by exact normalized name.

Only writes ``clients.copper_company_id``; never renames or merges anything.
Ambiguous cases are returned for a human to resolve.
"""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB

logger = structlog.get_logger()

ReviewReason = Literal["ambiguous_in_copper", "duplicate_in_vizzhub", "not_in_copper"]


@dataclass(frozen=True)
class CopperCompanyRef:
    id: int
    name: str
    email_domain: str | None = None
    created_on: date | None = None
    interaction_count: int = 0

    @classmethod
    def from_api(cls, company: dict) -> "CopperCompanyRef":
        created = company.get("date_created")
        return cls(
            id=company["id"],
            name=company["name"],
            email_domain=company.get("email_domain") or None,
            created_on=datetime.fromtimestamp(created, UTC).date() if created else None,
            interaction_count=company.get("interaction_count") or 0,
        )


@dataclass(frozen=True)
class ReviewItem:
    client_id: UUID
    client_name: str
    reason: ReviewReason
    candidates: list[CopperCompanyRef] = field(default_factory=list)


@dataclass
class LinkReport:
    linked: int = 0
    already_linked: int = 0
    review: list[ReviewItem] = field(default_factory=list)


def name_key(name: str) -> str:
    """Case-, accent-, spacing- and punctuation-insensitive key ("Sky Truth" == "SkyTruth")."""
    value = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", value.lower())


async def link_clients_to_copper(db: AsyncSession, companies: list[dict]) -> LinkReport:
    project_counts = (
        select(ProjectDB.client_id, func.count().label("n"))
        .group_by(ProjectDB.client_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(ClientDB, func.coalesce(project_counts.c.n, 0))
            .outerjoin(project_counts, project_counts.c.client_id == ClientDB.id)
            .where(ClientDB.is_active.is_(True))
        )
    ).all()

    report = LinkReport()
    taken = {c.copper_company_id for c, _ in rows if c.copper_company_id is not None}
    report.already_linked = len(taken)

    by_name: dict[str, list[CopperCompanyRef]] = defaultdict(list)
    for company in companies:
        if company["id"] not in taken:
            by_name[name_key(company["name"])].append(CopperCompanyRef.from_api(company))
    taken_names = {name_key(company["name"]) for company in companies if company["id"] in taken}

    clients_by_name: dict[str, list[tuple[ClientDB, int]]] = defaultdict(list)
    for client, n_projects in rows:
        if client.copper_company_id is None:
            clients_by_name[name_key(client.name)].append((client, n_projects))

    for key, group in clients_by_name.items():
        _resolve_group(group, by_name.get(key, []), key in taken_names, report)

    await db.flush()
    logger.info(
        "clients_copper_linked",
        linked=report.linked,
        already_linked=report.already_linked,
        review=len(report.review),
    )
    return report


def _resolve_group(
    group: list[tuple[ClientDB, int]],
    candidates: list[CopperCompanyRef],
    name_already_linked: bool,
    report: LinkReport,
) -> None:
    """Link or queue for review every unlinked client sharing one normalized name."""
    if len(candidates) > 1:
        # Spelling only disambiguates the 1:1 copies the initial import made.
        unresolved = (
            _link_by_exact_spelling(group, candidates, report)
            if len(group) == len(candidates)
            else group
        )
        report.review += [_item(c, "ambiguous_in_copper", candidates) for c, _ in unresolved]
        return
    if not candidates:
        reason: ReviewReason = "duplicate_in_vizzhub" if name_already_linked else "not_in_copper"
        report.review += [_item(c, reason, []) for c, _ in group]
        return
    company = candidates[0]
    ranked = sorted(group, key=lambda pair: (-pair[1], pair[0].name))
    ranked[0][0].copper_company_id = company.id
    report.linked += 1
    report.review += [_item(c, "duplicate_in_vizzhub", [company]) for c, _ in ranked[1:]]


def _link_by_exact_spelling(
    group: list[tuple[ClientDB, int]],
    candidates: list[CopperCompanyRef],
    report: LinkReport,
) -> list[tuple[ClientDB, int]]:
    """Link clients whose exact name matches exactly one candidate; return the rest.

    Same-name pairs usually come from the initial import copying Copper's own
    duplicates, so an exact spelling ("AidEnvironment" vs "aidenvironment") is
    the only signal left. Identical names stay unresolved for a human.
    """
    spelled: dict[str, list[CopperCompanyRef]] = defaultdict(list)
    for company in candidates:
        spelled[company.name].append(company)
    clients_spelled: dict[str, list[ClientDB]] = defaultdict(list)
    for client, _ in group:
        clients_spelled[client.name].append(client)

    unresolved: list[tuple[ClientDB, int]] = []
    for pair in group:
        client = pair[0]
        exact = spelled.get(client.name, [])
        if len(exact) == 1 and len(clients_spelled[client.name]) == 1:
            client.copper_company_id = exact[0].id
            report.linked += 1
        else:
            unresolved.append(pair)
    return unresolved


def _item(client: ClientDB, reason: ReviewReason, candidates: list[CopperCompanyRef]) -> ReviewItem:
    return ReviewItem(
        client_id=client.id, client_name=client.name, reason=reason, candidates=list(candidates)
    )
