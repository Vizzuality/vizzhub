"""Project CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, get_project_or_404, limiter
from app.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate

router = APIRouter()


@router.get("", response_model=list[Project])
@limiter.limit("100/minute")
async def list_projects(
    request: Request, current_user: CurrentUser, db: DBSession
) -> list[Project]:
    """List all projects. Requires authentication."""
    result = await db.execute(select(ProjectDB))
    projects = result.scalars().all()
    return [Project.model_validate(p) for p in projects]


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
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
    )
    db.add(db_project)
    await db.flush()
    await db.refresh(db_project)
    return Project.model_validate(db_project)


@router.get("/{project_id}", response_model=Project)
@limiter.limit("100/minute")
async def get_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> Project:
    """Get a project by ID. Requires authentication."""
    project = await get_project_or_404(db, project_id)
    return Project.model_validate(project)


@router.patch("/{project_id}", response_model=Project)
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


@router.put("/{project_id}", response_model=Project)
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

    await db.flush()
    await db.refresh(project)
    return Project.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> None:
    """Delete a project. Requires authentication."""
    project = await get_project_or_404(db, project_id)

    await db.delete(project)
