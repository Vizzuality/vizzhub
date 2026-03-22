"""Project CRUD endpoints (/api/projects)."""

import calendar
import math
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from app.config import get_scoring_config
from app.core.api.deps import (
    CurrentUser,
    DBSession,
    OptionalScoreCache,
    get_project_or_404,
    limiter,
)
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

ProjectManager = Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]
from app.core.models.link import Link, LinkCreate, LinkDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectCreateV2, ProjectDB, ProjectResponse, ProjectUpdate
from app.core.models.user import UserDB
from app.modules.scorecard.api.schemas.project import PaginatedProjectsResponse, ProjectSummary
from app.modules.scorecard.models.metrics.db import MetricsDB
from app.modules.scorecard.public import MetricsService, Milestone, SnapshotType, refresh_tracker_evm

router = APIRouter()

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
) -> list:
    """Build SQLAlchemy filter clauses for project listing."""
    filters = []
    if has_scorecard is not None:
        filters.append(ProjectDB.has_scorecard.is_(has_scorecard))
    if search:
        safe = _escape_like(search)
        filters.append(
            (ProjectDB.name.ilike(f"%{safe}%")) | (ProjectDB.code.ilike(f"%{safe}%"))
        )
    if filter_status and filter_status in ("proposal", "live", "finished"):
        filters.append(ProjectDB.status == filter_status)
    if start_date_from:
        filters.append(ProjectDB.start_date >= start_date_from)
    if start_date_to:
        filters.append(ProjectDB.start_date <= start_date_to)
    return filters


def _user_full_name_expr(user_alias):
    """SQL expression for user full name, NULL when both names are absent."""
    return func.nullif(
        func.trim(func.concat_ws(" ", user_alias.first_name, user_alias.last_name)),
        "",
    )


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
    project.budget = data.budget
    project.notes = data.notes
    project.summary = data.summary
    project.jira_project_key = (
        data.jira_project_key.upper() if data.jira_project_key else None
    )
    project.github_repo = data.github_repo
    project.start_date = data.start_date
    project.end_date = data.end_date
    project.status = data.status.value if data.status else "proposal"
    project.slack_channel_id = data.slack_channel_id
    project.project_manager_id = data.project_manager_id


@router.get("")
@limiter.limit("100/minute")
async def list_projects(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    lightweight: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 45,
    search: str | None = None,
    filter_status: Annotated[str | None, Query(alias="status")] = None,
    sort: str | None = None,
    order: str | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    has_scorecard: bool | None = None,
):
    if lightweight:
        q = select(ProjectDB).order_by(ProjectDB.name)
        if has_scorecard is not None:
            q = q.where(ProjectDB.has_scorecard.is_(has_scorecard))
        if filter_status and filter_status in ("proposal", "live", "finished"):
            q = q.where(ProjectDB.status == filter_status)
        result = await db.execute(q)
        projects = result.scalars().all()
        return [ProjectSummary.model_validate(p) for p in projects]

    program = aliased(ProgramDB)
    manager = aliased(UserDB)
    query = (
        select(
            ProjectDB,
            program.name.label("program_name"),
            _user_full_name_expr(manager).label("pm_name"),
        )
        .outerjoin(program, ProjectDB.program_id == program.id)
        .outerjoin(manager, ProjectDB.project_manager_id == manager.id)
    )
    count_query = select(func.count()).select_from(ProjectDB)

    filters = _build_project_filters(
        search, filter_status, start_date_from, start_date_to, has_scorecard,
    )
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    sort_field = sort if sort in ALLOWED_SORT_FIELDS else "created_at"
    sort_order = order if order in ("asc", "desc") else "desc"
    sort_column = getattr(ProjectDB, sort_field)
    query = query.order_by(
        sort_column.asc() if sort_order == "asc" else sort_column.desc()
    )

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()
    items = [
        _project_to_response(proj, program_name=pname, project_manager_name=pmname)
        for proj, pname, pmname in rows
    ]

    return PaginatedProjectsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


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
    return _project_to_response(db_project)


@router.get("/{project_id}", responses={404: {"description": "Project not found"}})
@limiter.limit("100/minute")
async def get_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> ProjectResponse:
    program = aliased(ProgramDB)
    manager = aliased(UserDB)
    result = await db.execute(
        select(
            ProjectDB,
            program.name.label("program_name"),
            _user_full_name_expr(manager).label("pm_name"),
        )
        .outerjoin(program, ProjectDB.program_id == program.id)
        .outerjoin(manager, ProjectDB.project_manager_id == manager.id)
        .where(ProjectDB.id == project_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    proj, pname, pmname = row
    return _project_to_response(proj, program_name=pname, project_manager_name=pmname)


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
    await db.refresh(project)
    if project.budget != old_budget or project.start_date != old_start or project.end_date != old_end:
        await refresh_tracker_evm(db, project_id, score_cache=cache)
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
        "name", "code", "program_id", "is_billable", "currency", "budget",
        "notes", "summary", "jira_project_key", "github_repo",
        "start_date", "end_date", "status", "finished_at",
        "slack_channel_id", "has_scorecard", "has_dependabot_alerts",
        "has_budget_alerts", "project_manager_id",
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

    if "budget" in update_data or "start_date" in update_data or "end_date" in update_data:
        await refresh_tracker_evm(db, project_id, score_cache=cache)

    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"description": "Cannot delete: project has dependent records"}},
)
@limiter.limit("10/minute")
async def delete_project(
    request: Request, project_id: UUID, admin: ProjectManager, db: DBSession
) -> None:
    project = await get_project_or_404(db, project_id)

    from app.modules.tracker.public import has_tracker_references

    tracker_refs = await has_tracker_references(project_id, db)
    if tracker_refs:
        raise HTTPException(status_code=409, detail=tracker_refs[0])

    await db.execute(delete(MetricsDB).where(MetricsDB.project_id == project_id))
    await db.delete(project)


# ---------------------------------------------------------------------------
# Budget (EVM + milestones) endpoint
# ---------------------------------------------------------------------------


class ProjectBudgetUpdate(BaseModel):
    milestones: list[Milestone] | None = None


def _metrics_to_budget_response(metrics: MetricsDB, year: int, month: int) -> dict:
    """Build budget response from metrics DB record."""
    milestones = metrics.milestones if metrics.milestones else []
    return {
        "period_year": year,
        "period_month": month,
        "milestones": milestones,
    }


@router.put("/{project_id}/budget")
@limiter.limit("60/minute")
async def update_project_budget(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    project_id: UUID,
    payload: ProjectBudgetUpdate,
    cache: OptionalScoreCache,
) -> dict:
    """Update milestones and budget_total for current period.

    EVM fields (cost_to_date, percent_completed, percent_planned) are now
    derived from the tracker module, not manually entered.
    """
    project = await get_project_or_404(db, project_id)

    today = date.today()
    year, month = today.year, today.month
    config = get_scoring_config()

    data: dict = {
        "period_start": date(year, month, 1),
        "period_end": date(year, month, calendar.monthrange(year, month)[1]),
    }
    if project.budget is not None:
        data["budget_total"] = float(project.budget)
    if payload.milestones is not None:
        data["milestones"] = [m.model_dump(mode="json") for m in payload.milestones]

    has_budget_data = any(
        k not in ("period_start", "period_end") for k in data
    )
    if not has_budget_data:
        existing = await MetricsService.get_metrics(db, str(project_id), year, month)
        if existing:
            return _metrics_to_budget_response(existing, year, month)
        return {"period_year": year, "period_month": month, "milestones": []}

    metrics = await MetricsService.upsert_metrics(
        db, project_id, year, month, SnapshotType.CUMULATIVE, config, data
    )

    await refresh_tracker_evm(db, project_id, score_cache=cache)

    return _metrics_to_budget_response(metrics, year, month)


# --- Links ---


@router.get("/{project_id}/links")
@limiter.limit("100/minute")
async def get_project_links(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    project_id: UUID,
) -> list[Link]:
    """Get all links for a project."""
    await get_project_or_404(db, project_id)

    link_type_order = func.array_position(
        ["code", "project-management", "app-environments", "design"],
        LinkDB.link_type,
    )
    result = await db.execute(
        select(LinkDB)
        .where(LinkDB.project_id == project_id)
        .order_by(link_type_order, LinkDB.title)
    )
    return [Link.model_validate(row) for row in result.scalars().all()]


class ProjectLinkInput(BaseModel):
    title: str | None = None
    url: str | None = None
    link_type: str | None = None


@router.put("/{project_id}/links")
@limiter.limit("30/minute")
async def replace_project_links(
    request: Request,
    current_user: ProjectManager,
    db: DBSession,
    project_id: UUID,
    payload: list[ProjectLinkInput],
) -> list[Link]:
    """Replace all links for a project. Deletes existing and creates new ones."""
    await get_project_or_404(db, project_id)

    await db.execute(delete(LinkDB).where(LinkDB.project_id == project_id))

    new_links = []
    for link_data in payload:
        if not link_data.title and not link_data.url:
            continue
        link = LinkDB(
            project_id=project_id,
            title=link_data.title,
            url=link_data.url,
            link_type=link_data.link_type,
        )
        db.add(link)
        new_links.append(link)

    await db.flush()
    for link in new_links:
        await db.refresh(link)

    return [Link.model_validate(link) for link in new_links]
