"""Project CRUD endpoints (/api/projects)."""

import math
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from app.core.api.deps import AdminUser, CurrentUser, DBSession, get_project_or_404, limiter
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectCreateV2, ProjectDB, ProjectResponse, ProjectUpdate
from app.modules.scorecard.api.schemas.project import PaginatedProjectsResponse, ProjectSummary
from app.modules.scorecard.models.metrics.db import MetricsDB

router = APIRouter()

ALLOWED_SORT_FIELDS = {"name", "created_at", "status"}
MAX_PAGE_SIZE = 100


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _project_to_response(
    project: ProjectDB, program_name: str | None = None
) -> ProjectResponse:
    data = {c.key: getattr(project, c.key) for c in project.__table__.columns}
    data["program_name"] = program_name
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
        result = await db.execute(q)
        projects = result.scalars().all()
        return [ProjectSummary.model_validate(p) for p in projects]

    program = aliased(ProgramDB)
    query = (
        select(ProjectDB, program.name.label("program_name"))
        .outerjoin(program, ProjectDB.program_id == program.id)
    )
    count_query = select(func.count()).select_from(ProjectDB)

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
    items = [_project_to_response(row[0], row[1]) for row in rows]

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
    request: Request, project: ProjectCreateV2, admin: AdminUser, db: DBSession
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
    result = await db.execute(
        select(ProjectDB, program.name.label("program_name"))
        .outerjoin(program, ProjectDB.program_id == program.id)
        .where(ProjectDB.id == project_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(row[0], row[1])


@router.put("/{project_id}")
@limiter.limit("30/minute")
async def replace_project(
    request: Request,
    project_id: UUID,
    data: ProjectCreateV2,
    admin: AdminUser,
    db: DBSession,
) -> ProjectResponse:
    project = await get_project_or_404(db, project_id)
    _apply_project_data(project, data)
    await db.flush()
    await db.refresh(project)
    return _project_to_response(project)


@router.patch("/{project_id}")
@limiter.limit("30/minute")
async def update_project(
    request: Request,
    project_id: UUID,
    update: ProjectUpdate,
    admin: AdminUser,
    db: DBSession,
) -> ProjectResponse:
    PATCHABLE_FIELDS = {
        "name", "code", "program_id", "is_billable", "currency",
        "notes", "summary", "jira_project_key", "github_repo",
        "start_date", "end_date", "status", "finished_at",
        "slack_channel_id", "has_scorecard", "has_dependabot_alerts",
        "has_budget_alerts",
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
    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"description": "Cannot delete: project has dependent records"}},
)
@limiter.limit("10/minute")
async def delete_project(
    request: Request, project_id: UUID, admin: AdminUser, db: DBSession
) -> None:
    project = await get_project_or_404(db, project_id)

    from sqlalchemy import text

    table_check = await db.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('report_parts', 'progress_reports')")
    )
    existing_tables = {row[0] for row in table_check.fetchall()}

    if "report_parts" in existing_tables:
        from app.modules.tracker.models.report_part import ReportPartDB

        rp_count = (
            await db.execute(
                select(func.count())
                .select_from(ReportPartDB)
                .where(ReportPartDB.project_id == project_id)
            )
        ).scalar() or 0
        if rp_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete: project has {rp_count} time report entries.",
            )

    if "progress_reports" in existing_tables:
        from app.modules.tracker.models.progress_report import ProgressReportDB

        pr_count = (
            await db.execute(
                select(func.count())
                .select_from(ProgressReportDB)
                .where(ProgressReportDB.project_id == project_id)
            )
        ).scalar() or 0
        if pr_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete: project has {pr_count} progress reports.",
            )

    await db.execute(delete(MetricsDB).where(MetricsDB.project_id == project_id))
    await db.delete(project)
