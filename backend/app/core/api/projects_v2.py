"""Project CRUD endpoints (/api/projects)."""

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.core.api import projects_budget, projects_links
from app.core.api.deps import (
    CurrentUser,
    DBSession,
    OptionalScoreCache,
    ProjectManager,
    get_project_or_404,
    limiter,
)
from app.core.models.client import ClientDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectCreateV2, ProjectDB, ProjectResponse, ProjectUpdate
from app.core.models.user import UserDB
from app.core.services.project_provisioning import provision_project_accrual
from app.core.sql_helpers import user_display_name_expr
from app.modules.accrual.public import convert_original_budget
from app.modules.scorecard.public import (
    PaginatedProjectsResponse,
    ProjectSummary,
    delete_project_metrics,
    refresh_tracker_evm,
)

logger = structlog.get_logger()

router = APIRouter()
router.include_router(projects_budget.router)
router.include_router(projects_links.router)

ALLOWED_SORT_FIELDS = {"name", "created_at", "status"}
MAX_PAGE_SIZE = 100


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_project_filters(
    search: str | None,
    filter_status: str | None,
    start_date_from: date | None,
    start_date_to: date | None,
    has_scorecard: bool | None,
    project_manager_id: UUID | None = None,
) -> list:
    """Build SQLAlchemy filter clauses for project listing."""
    filters = []
    if has_scorecard is not None:
        filters.append(ProjectDB.has_scorecard.is_(has_scorecard))
    if search:
        safe = _escape_like(search)
        filters.append((ProjectDB.name.ilike(f"%{safe}%")) | (ProjectDB.code.ilike(f"%{safe}%")))
    if filter_status and filter_status in ("proposal", "live", "finished"):
        filters.append(ProjectDB.status == filter_status)
    if start_date_from:
        filters.append(ProjectDB.start_date >= start_date_from)
    if start_date_to:
        filters.append(ProjectDB.start_date <= start_date_to)
    if project_manager_id:
        filters.append(ProjectDB.project_manager_id == project_manager_id)
    return filters


def _project_to_response(project: ProjectDB, **extras) -> ProjectResponse:
    data = {c.key: getattr(project, c.key) for c in project.__table__.columns}
    data.update(extras)
    return ProjectResponse.model_validate(data)


def _apply_project_data(project: ProjectDB, data: ProjectCreateV2) -> None:
    """Set all fields from the schema onto the model instance."""
    project.name = data.name
    project.code = data.code
    project.program_id = data.program_id
    project.is_billable = data.is_billable
    project.has_scorecard = data.has_scorecard
    project.has_dependabot_alerts = data.has_dependabot_alerts
    project.has_budget_alerts = data.has_budget_alerts
    project.currency = data.currency
    # budget is a derived field: provision_project_accrual recomputes it from
    # original_budget + the period FX rate. Only honour an explicit incoming budget;
    # never null an existing value when the caller omits it (the form does), so an
    # underivable edit (no rate) preserves the prior budget instead of wiping it.
    if data.budget is not None:
        project.budget = data.budget
    project.original_budget = data.original_budget
    project.notes = data.notes
    project.summary = data.summary
    project.jira_project_key = data.jira_project_key.upper() if data.jira_project_key else None
    project.github_repo = data.github_repo
    project.start_date = data.start_date
    project.end_date = data.end_date
    project.status = data.status.value if data.status else "proposal"
    project.slack_channel_id = data.slack_channel_id
    project.project_manager_id = data.project_manager_id
    project.client_id = data.client_id


@dataclass
class ProjectListFilters:
    search: str | None = None
    filter_status: Annotated[str | None, Query(alias="status")] = None
    start_date_from: date | None = None
    start_date_to: date | None = None
    has_scorecard: bool | None = None
    project_manager_id: UUID | None = None


@router.get("")
@limiter.limit("100/minute")
async def list_projects(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    f: Annotated[ProjectListFilters, Depends()],
    lightweight: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 45,
    sort: str | None = None,
    order: str | None = None,
):
    if lightweight:
        q = select(ProjectDB).order_by(ProjectDB.name)
        if f.has_scorecard is not None:
            q = q.where(ProjectDB.has_scorecard.is_(f.has_scorecard))
        if f.filter_status and f.filter_status in ("proposal", "live", "finished"):
            q = q.where(ProjectDB.status == f.filter_status)
        if f.project_manager_id:
            q = q.where(ProjectDB.project_manager_id == f.project_manager_id)
        result = await db.execute(q)
        projects = result.scalars().all()
        return [ProjectSummary.model_validate(p) for p in projects]

    program = aliased(ProgramDB)
    manager = aliased(UserDB)
    client = aliased(ClientDB)
    query = (
        select(
            ProjectDB,
            program.name.label("program_name"),
            user_display_name_expr(manager).label("pm_name"),
            client.name.label("client_name"),
        )
        .outerjoin(program, ProjectDB.program_id == program.id)
        .outerjoin(manager, ProjectDB.project_manager_id == manager.id)
        .outerjoin(client, ProjectDB.client_id == client.id)
    )
    count_query = select(func.count()).select_from(ProjectDB)

    filters = _build_project_filters(
        f.search,
        f.filter_status,
        f.start_date_from,
        f.start_date_to,
        f.has_scorecard,
        f.project_manager_id,
    )
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    sort_field = sort if sort in ALLOWED_SORT_FIELDS else "created_at"
    sort_order = order if order in ("asc", "desc") else "desc"
    sort_column = getattr(ProjectDB, sort_field)
    query = query.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()
    items = [
        _project_to_response(
            proj, program_name=pname, project_manager_name=pmname, client_name=cname
        )
        for proj, pname, pmname, cname in rows
    ]

    return PaginatedProjectsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


class ProjectManagerOption(BaseModel):
    id: str
    name: str


class BudgetPreviewResponse(BaseModel):
    budget_eur: float | None


@router.get("/project-managers")
async def list_project_managers(
    current_user: CurrentUser,
    db: DBSession,
) -> list[ProjectManagerOption]:
    """Distinct project managers assigned to at least one project."""
    manager = aliased(UserDB)
    display_name = user_display_name_expr(manager).label("display_name")
    result = await db.execute(
        select(manager.id, display_name)
        .join(ProjectDB, ProjectDB.project_manager_id == manager.id)
        .where(manager.active.is_(True))
        .distinct()
        .order_by("display_name")
    )
    return [ProjectManagerOption(id=str(row.id), name=row.display_name) for row in result.all()]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_project(
    request: Request, project: ProjectCreateV2, admin: ProjectManager, db: DBSession
) -> ProjectResponse:
    db_project = ProjectDB()
    _apply_project_data(db_project, project)
    db.add(db_project)
    await db.flush()
    await db.refresh(db_project)
    await provision_project_accrual(db, project=db_project)
    await db.refresh(db_project)
    logger.info(
        "project_created",
        project_id=str(db_project.id),
        code=db_project.code,
        user_id=admin.user_id,
    )
    return _project_to_response(db_project)


@router.get("/budget-preview")
@limiter.limit("120/minute")
async def budget_preview(
    request: Request,
    current_user: ProjectManager,
    db: DBSession,
    original_budget: Annotated[float, Query(ge=0)],
    currency: str,
    start_date: date,
) -> BudgetPreviewResponse:
    """Preview the derived EUR budget for the project form (read-only).

    Delegates to accrual's FX math; returns budget_eur=None when no rate resolves.
    """
    eur = await convert_original_budget(
        db,
        original_budget=Decimal(str(original_budget)),
        currency=currency,
        start_date=start_date,
    )
    return BudgetPreviewResponse(budget_eur=float(eur) if eur is not None else None)


@router.get("/{project_id}", responses={404: {"description": "Project not found"}})
@limiter.limit("100/minute")
async def get_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> ProjectResponse:
    program = aliased(ProgramDB)
    manager = aliased(UserDB)
    client = aliased(ClientDB)
    result = await db.execute(
        select(
            ProjectDB,
            program.name.label("program_name"),
            user_display_name_expr(manager).label("pm_name"),
            client.name.label("client_name"),
        )
        .outerjoin(program, ProjectDB.program_id == program.id)
        .outerjoin(manager, ProjectDB.project_manager_id == manager.id)
        .outerjoin(client, ProjectDB.client_id == client.id)
        .where(ProjectDB.id == project_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    proj, pname, pmname, cname = row
    return _project_to_response(
        proj, program_name=pname, project_manager_name=pmname, client_name=cname
    )


@router.put("/{project_id}")
@limiter.limit("30/minute")
async def replace_project(
    request: Request,
    project_id: UUID,
    data: ProjectCreateV2,
    admin: ProjectManager,
    db: DBSession,
    cache: OptionalScoreCache,
) -> ProjectResponse:
    project = await get_project_or_404(db, project_id)
    old_budget, old_start, old_end = project.budget, project.start_date, project.end_date
    _apply_project_data(project, data)
    await db.flush()
    result = await provision_project_accrual(db, project=project)
    await db.refresh(project)
    if (
        project.budget != old_budget
        or project.start_date != old_start
        or project.end_date != old_end
        or result.budget_changed
    ):
        await refresh_tracker_evm(db, project_id, score_cache=cache)
    logger.info(
        "project_replaced",
        project_id=str(project_id),
        user_id=admin.user_id,
    )
    return _project_to_response(project)


@router.patch("/{project_id}")
@limiter.limit("30/minute")
async def update_project(
    request: Request,
    project_id: UUID,
    update: ProjectUpdate,
    admin: ProjectManager,
    db: DBSession,
    cache: OptionalScoreCache,
) -> ProjectResponse:
    PATCHABLE_FIELDS = {
        "name",
        "code",
        "program_id",
        "is_billable",
        "currency",
        "budget",
        "original_budget",
        "notes",
        "summary",
        "jira_project_key",
        "github_repo",
        "start_date",
        "end_date",
        "status",
        "finished_at",
        "slack_channel_id",
        "has_scorecard",
        "has_dependabot_alerts",
        "has_budget_alerts",
        "project_manager_id",
        "client_id",
    }

    project = await get_project_or_404(db, project_id)
    update_data = update.model_dump(exclude_unset=True)
    if update_data.pop("clear_finished_at", False):
        project.finished_at = None
    for field, value in update_data.items():
        if field not in PATCHABLE_FIELDS:
            continue
        if field == "jira_project_key" and value:
            value = value.upper()
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    result = await provision_project_accrual(db, project=project)
    await db.refresh(project)

    if (
        "budget" in update_data
        or "start_date" in update_data
        or "end_date" in update_data
        or "original_budget" in update_data
        or result.budget_changed
    ):
        await refresh_tracker_evm(db, project_id, score_cache=cache)

    logger.info(
        "project_updated",
        project_id=str(project_id),
        fields=sorted(update_data.keys()),
        user_id=admin.user_id,
    )
    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"description": "Cannot delete: project has dependent records"}},
)
@limiter.limit("10/minute")
async def delete_project(
    request: Request,
    project_id: UUID,
    admin: ProjectManager,
    db: DBSession,
    cache: OptionalScoreCache,
) -> None:
    project = await get_project_or_404(db, project_id)

    from app.modules.tracker.public import has_tracker_references

    tracker_refs = await has_tracker_references(project_id, db)
    if tracker_refs:
        raise HTTPException(status_code=409, detail=tracker_refs[0])

    await delete_project_metrics(db, project_id)
    await db.delete(project)
    if cache:
        await cache.invalidate(str(project_id))
    logger.info(
        "project_deleted",
        project_id=str(project_id),
        code=project.code,
        user_id=admin.user_id,
    )
