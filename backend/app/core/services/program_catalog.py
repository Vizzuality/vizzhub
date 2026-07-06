"""Program catalogue — grouped portfolio reads + profile/terms writes (F2).

Lives in core/services because it reads and writes core entities (programs,
projects, clients, portfolio_profile, entity_terms) on behalf of the
portfolio module (architecture rule 4, same layering as portfolio_dashboard).
Index filters run in Python: the catalogue is ~150 programs, one pass over
three batched IN() queries beats SQL EXISTS gymnastics and stays testable.
"""

from collections import defaultdict
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.modules.portfolio.schemas.programs import (
    ClientRef,
    ProfileFields,
    ProgramIndexResponse,
    ProgramSummary,
    ProjectIteration,
    TermChip,
)

logger = structlog.get_logger()


def _iteration(project: ProjectDB, client_name: str | None) -> ProjectIteration:
    return ProjectIteration(
        id=project.id,
        name=project.name,
        status=project.status,
        start_year=project.start_date.year if project.start_date else None,
        end_year=project.end_date.year if project.end_date else None,
        has_scorecard=project.has_scorecard,
        is_billable=project.is_billable,
        is_absence=project.is_absence,
        client_id=project.client_id,
        client_name=client_name,
    )


async def _terms_by_program(
    db: AsyncSession, program_ids: list[UUID]
) -> dict[UUID, list[TermChip]]:
    rows = (
        await db.execute(
            select(EntityTermDB, TaxonomyTermDB, TaxonomyDB.slug)
            .join(TaxonomyTermDB, TaxonomyTermDB.id == EntityTermDB.term_id)
            .join(TaxonomyDB, TaxonomyDB.id == EntityTermDB.taxonomy_id)
            .where(EntityTermDB.program_id.in_(program_ids))
            .order_by(TaxonomyDB.sort_order, TaxonomyTermDB.sort_order, TaxonomyTermDB.name)
        )
    ).all()
    out: dict[UUID, list[TermChip]] = defaultdict(list)
    for assoc, term, tax_slug in rows:
        out[assoc.program_id].append(
            TermChip(
                term_id=term.id,
                taxonomy_id=assoc.taxonomy_id,
                taxonomy_slug=tax_slug,
                name=term.name,
                is_primary=assoc.is_primary,
            )
        )
    return out


async def _assemble(db: AsyncSession, programs: list[ProgramDB]) -> list[ProgramSummary]:
    ids = [p.id for p in programs]
    if not ids:
        return []
    profile_rows = (
        (await db.execute(select(PortfolioProfileDB).where(PortfolioProfileDB.program_id.in_(ids))))
        .scalars()
        .all()
    )
    profiles = {row.program_id: ProfileFields.model_validate(row) for row in profile_rows}
    terms = await _terms_by_program(db, ids)
    project_rows = (
        await db.execute(
            select(ProjectDB, ClientDB.name)
            .outerjoin(ClientDB, ClientDB.id == ProjectDB.client_id)
            .where(ProjectDB.program_id.in_(ids))
            .order_by(ProjectDB.start_date.desc().nulls_last(), ProjectDB.name)
        )
    ).all()
    projects: dict[UUID, list[ProjectIteration]] = defaultdict(list)
    clients: dict[UUID, dict[UUID, ClientRef]] = defaultdict(dict)
    for project, client_name in project_rows:
        projects[project.program_id].append(_iteration(project, client_name))
        if project.client_id is not None:
            clients[project.program_id][project.client_id] = ClientRef(
                id=project.client_id, name=client_name or ""
            )
    return [
        ProgramSummary(
            id=p.id,
            name=p.name,
            profile=profiles.get(p.id),
            terms=terms.get(p.id, []),
            clients=sorted(clients.get(p.id, {}).values(), key=lambda c: c.name),
            projects=projects.get(p.id, []),
        )
        for p in programs
    ]


async def build_program_detail(db: AsyncSession, program_id: UUID) -> ProgramSummary | None:
    program = (
        await db.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    ).scalar_one_or_none()
    if program is None:
        return None
    return (await _assemble(db, [program]))[0]


def _passes_term_filter(chips: list[TermChip], groups: dict[UUID, set[UUID]]) -> bool:
    """OR within a taxonomy group, AND across groups."""
    have = {c.term_id for c in chips}
    return all(have & wanted for wanted in groups.values())


async def build_program_index(
    db: AsyncSession,
    *,
    search: str = "",
    term_ids: list[UUID] | None = None,
    client_id: UUID | None = None,
) -> ProgramIndexResponse:
    programs = (await db.execute(select(ProgramDB).order_by(ProgramDB.name))).scalars().all()
    summaries = await _assemble(db, list(programs))
    needle = search.strip().lower()
    if needle:
        summaries = [s for s in summaries if needle in s.name.lower()]
    if client_id is not None:
        summaries = [s for s in summaries if any(c.id == client_id for c in s.clients)]
    if term_ids:
        term_rows = (
            await db.execute(
                select(TaxonomyTermDB.id, TaxonomyTermDB.taxonomy_id).where(
                    TaxonomyTermDB.id.in_(term_ids)
                )
            )
        ).all()
        groups: dict[UUID, set[UUID]] = defaultdict(set)
        for tid, taxonomy_id in term_rows:
            groups[taxonomy_id].add(tid)
        summaries = [s for s in summaries if _passes_term_filter(s.terms, groups)]
    unassigned_rows = (
        await db.execute(
            select(ProjectDB, ClientDB.name)
            .outerjoin(ClientDB, ClientDB.id == ProjectDB.client_id)
            .where(ProjectDB.program_id.is_(None), ProjectDB.is_absence.is_(False))
            .order_by(ProjectDB.name)
        )
    ).all()
    return ProgramIndexResponse(
        programs=summaries,
        unassigned_projects=[_iteration(p, cn) for p, cn in unassigned_rows],
    )
