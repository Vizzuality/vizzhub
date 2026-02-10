"""Project CRUD endpoints."""

import math
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import delete, func, select

from app.api.deps import CurrentUser, DBSession, get_project_or_404, limiter
from app.api.schemas.project import PaginatedProjectsResponse, ProjectSummary
from app.models.metrics.db import MetricsDB
from app.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate

router = APIRouter()

ALLOWED_SORT_FIELDS = {"name", "created_at", "status"}
MAX_PAGE_SIZE = 100


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
@limiter.limit("100/minute")
async def list_projects(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    lightweight: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(45, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = None,
    filter_status: str | None = Query(None, alias="status"),
    sort: str | None = None,
    order: str | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
) -> PaginatedProjectsResponse | list[ProjectSummary]:
    """List projects with pagination, filtering, and sorting."""
    if lightweight:
        result = await db.execute(
            select(ProjectDB).order_by(ProjectDB.name)
        )
        projects = result.scalars().all()
        return [ProjectSummary.model_validate(p) for p in projects]

    filters = []

    if search:
        safe = _escape_like(search)
        filters.append(ProjectDB.name.ilike(f"%{safe}%"))

    if filter_status and filter_status in ("in_progress", "finished"):
        filters.append(ProjectDB.status == filter_status)

    if start_date_from:
        filters.append(ProjectDB.start_date >= start_date_from)

    if start_date_to:
        filters.append(ProjectDB.start_date <= start_date_to)

    query = select(ProjectDB).where(*filters)
    count_query = select(func.count()).select_from(ProjectDB).where(*filters)

    sort_field = sort if sort in ALLOWED_SORT_FIELDS else "created_at"
    sort_order = order if order in ("asc", "desc") else "desc"
    sort_column = getattr(ProjectDB, sort_field)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    projects = result.scalars().all()

    return PaginatedProjectsResponse(
        items=[Project.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_project(
    request: Request, project: ProjectCreate, current_user: CurrentUser, db: DBSession
) -> Project:
    """Create a new project. Requires authentication."""
    db_project = ProjectDB(
        name=project.name,
        jira_project_key=project.jira_project_key.upper() if project.jira_project_key else None,
        github_repo=project.github_repo,
        start_date=project.start_date,
        end_date=project.end_date,
        slack_channel_id=project.slack_channel_id,
    )
    db.add(db_project)
    await db.flush()
    await db.refresh(db_project)
    return Project.model_validate(db_project)


@router.get("/{project_id}")
@limiter.limit("100/minute")
async def get_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> Project:
    """Get a project by ID. Requires authentication."""
    project = await get_project_or_404(db, project_id)
    return Project.model_validate(project)


@router.patch("/{project_id}")
@limiter.limit("30/minute")
async def update_project(
    request: Request,
    project_id: UUID,
    update: ProjectUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> Project:
    """Partially update a project. Requires authentication."""
    project = await get_project_or_404(db, project_id)

    update_data = update.model_dump(exclude_unset=True)

    # Handle clear_finished_at flag
    if update_data.pop("clear_finished_at", False):
        project.finished_at = None

    for field, value in update_data.items():
        if field == "jira_project_key" and value:
            value = value.upper()
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return Project.model_validate(project)


@router.put("/{project_id}")
@limiter.limit("30/minute")
async def replace_project(
    request: Request,
    project_id: UUID,
    project_data: ProjectCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> Project:
    """Fully replace a project. Requires authentication."""
    project = await get_project_or_404(db, project_id)

    project.name = project_data.name
    project.jira_project_key = project_data.jira_project_key.upper() if project_data.jira_project_key else None
    project.github_repo = project_data.github_repo
    project.start_date = project_data.start_date
    project.end_date = project_data.end_date
    project.slack_channel_id = project_data.slack_channel_id

    await db.flush()
    await db.refresh(project)
    return Project.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> None:
    """Delete a project and all associated metrics. Requires authentication."""
    project = await get_project_or_404(db, project_id)

    await db.execute(delete(MetricsDB).where(MetricsDB.project_id == project_id))
    await db.delete(project)
