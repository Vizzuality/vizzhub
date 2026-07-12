"""Program catalogue — grouped portfolio reads + profile/terms writes (F2).

Lives in core/services because it reads and writes core entities (programs,
projects, clients, portfolio_profile, entity_terms) on behalf of the
portfolio module (architecture rule 4, same layering as portfolio_dashboard).
Index filtering and pagination run in SQL (spec 2026-07-12).
"""

import math
from collections import defaultdict
from uuid import UUID

import structlog
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.modules.portfolio.schemas.programs import (
    ClientRef,
    ProfileFields,
    ProgramIndexResponse,
    ProgramProfileUpdate,
    ProgramSummary,
    ProgramTermsUpdate,
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


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


async def _term_groups(db: AsyncSession, term_ids: list[UUID]) -> dict[UUID, set[UUID]]:
    rows = (
        await db.execute(
            select(TaxonomyTermDB.id, TaxonomyTermDB.taxonomy_id).where(
                TaxonomyTermDB.id.in_(term_ids)
            )
        )
    ).all()
    groups: dict[UUID, set[UUID]] = defaultdict(set)
    for tid, taxonomy_id in rows:
        groups[taxonomy_id].add(tid)
    return groups


async def build_program_index(
    db: AsyncSession,
    *,
    search: str = "",
    term_ids: list[UUID] | None = None,
    client_id: UUID | None = None,
    stage: str | None = None,
    page: int = 1,
    n: int = 24,
) -> ProgramIndexResponse:
    query = select(ProgramDB).outerjoin(
        PortfolioProfileDB, PortfolioProfileDB.program_id == ProgramDB.id
    )

    needle = search.strip()
    tsq = func.websearch_to_tsquery("english", needle)
    if len(needle) >= 2:
        name_match = ProgramDB.name.ilike(f"%{_escape_like(needle)}%", escape="\\")
        vector_match = PortfolioProfileDB.search_vector.op("@@")(tsq)
        query = query.where(name_match | vector_match)
    if stage is not None:
        query = query.where(PortfolioProfileDB.stage == stage)
    if client_id is not None:
        query = query.where(
            exists(
                select(1).where(
                    ProjectDB.program_id == ProgramDB.id, ProjectDB.client_id == client_id
                )
            )
        )
    if term_ids:
        for wanted in (await _term_groups(db, term_ids)).values():
            query = query.where(
                exists(
                    select(1).where(
                        EntityTermDB.program_id == ProgramDB.id,
                        EntityTermDB.term_id.in_(wanted),
                    )
                )
            )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    pages = max(1, math.ceil(total / n))

    if len(needle) >= 2:
        query = query.order_by(
            ProgramDB.name.ilike(f"%{_escape_like(needle)}%", escape="\\").desc(),
            func.coalesce(func.ts_rank(PortfolioProfileDB.search_vector, tsq), 0).desc(),
            ProgramDB.name,
        )
        logger.info("program_search", query=needle, result_count=total)
    else:
        query = query.order_by(ProgramDB.name)
    query = query.offset((page - 1) * n).limit(n)

    programs = (await db.execute(query)).scalars().all()
    summaries = await _assemble(db, list(programs))
    return ProgramIndexResponse(programs=summaries, total=total, pages=pages)


async def _require_program(db: AsyncSession, program_id: UUID) -> ProgramDB:
    program = (
        await db.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    ).scalar_one_or_none()
    if program is None:
        raise LookupError("Program not found")
    return program


async def upsert_program_profile(
    db: AsyncSession, program_id: UUID, update: ProgramProfileUpdate
) -> ProfileFields:
    await _require_program(db, program_id)
    profile = (
        await db.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == program_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = PortfolioProfileDB(program_id=program_id)
        db.add(profile)
    for field in update.model_fields_set:
        value = getattr(update, field)
        if field == "on_website" and value is None:
            continue  # boolean column is NOT NULL; explicit null means "leave as is"
        setattr(profile, field, value)
    await db.flush()
    await db.refresh(profile)
    return ProfileFields.model_validate(profile)


async def list_unassigned_projects(db: AsyncSession) -> list[ProjectIteration]:
    rows = (
        await db.execute(
            select(ProjectDB, ClientDB.name)
            .outerjoin(ClientDB, ClientDB.id == ProjectDB.client_id)
            .where(ProjectDB.program_id.is_(None), ProjectDB.is_absence.is_(False))
            .order_by(ProjectDB.name)
        )
    ).all()
    return [_iteration(p, cn) for p, cn in rows]


async def list_program_stages(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(
            select(PortfolioProfileDB.stage)
            .distinct()
            .where(
                PortfolioProfileDB.program_id.is_not(None),
                PortfolioProfileDB.stage.is_not(None),
            )
            .order_by(PortfolioProfileDB.stage)
        )
    ).scalars()
    return list(rows)


async def replace_program_terms(
    db: AsyncSession,
    program_id: UUID,
    payload: ProgramTermsUpdate,
    assigned_by: UUID | None,
) -> list[TermChip]:
    await _require_program(db, program_id)
    taxonomy = (
        await db.execute(select(TaxonomyDB).where(TaxonomyDB.id == payload.taxonomy_id))
    ).scalar_one_or_none()
    if taxonomy is None:
        raise LookupError("Taxonomy not found")

    unique_ids = list(dict.fromkeys(payload.term_ids))
    if taxonomy.cardinality == Cardinality.SINGLE and len(unique_ids) > 1:
        raise ValueError("This taxonomy accepts at most one term")
    if payload.primary_term_id is not None:
        if not taxonomy.allows_primary:
            raise ValueError("This taxonomy does not allow a primary term")
        if payload.primary_term_id not in unique_ids:
            raise ValueError("Primary term must be among the assigned terms")

    term_rows = (
        (await db.execute(select(TaxonomyTermDB).where(TaxonomyTermDB.id.in_(unique_ids))))
        .scalars()
        .all()
        if unique_ids
        else []
    )
    found = {t.id: t for t in term_rows}
    for term_id in unique_ids:
        term = found.get(term_id)
        if term is None or term.taxonomy_id != taxonomy.id or not term.is_active:
            raise ValueError("Terms must be active members of the taxonomy")

    await db.execute(
        delete(EntityTermDB).where(
            EntityTermDB.program_id == program_id,
            EntityTermDB.taxonomy_id == taxonomy.id,
        )
    )
    for term_id in unique_ids:
        db.add(
            EntityTermDB(
                term_id=term_id,
                taxonomy_id=taxonomy.id,
                program_id=program_id,
                is_primary=term_id == payload.primary_term_id,
                assigned_by=assigned_by,
            )
        )
    await db.flush()
    return [
        TermChip(
            term_id=term_id,
            taxonomy_id=taxonomy.id,
            taxonomy_slug=taxonomy.slug,
            name=found[term_id].name,
            is_primary=term_id == payload.primary_term_id,
        )
        for term_id in unique_ids
    ]
