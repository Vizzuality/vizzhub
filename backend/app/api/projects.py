"""Project CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.core.exceptions import ProjectNotFoundError
from app.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate

router = APIRouter()


@router.get("", response_model=list[Project])
async def list_projects(db: DBSession) -> list[Project]:
    """List all projects."""
    result = await db.execute(select(ProjectDB))
    projects = result.scalars().all()
    return [Project.model_validate(p) for p in projects]


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: DBSession) -> Project:
    """Create a new project."""
    db_project = ProjectDB(
        name=project.name,
        jira_project_key=project.jira_project_key,
        github_repo=project.github_repo,
    )
    db.add(db_project)
    await db.flush()
    await db.refresh(db_project)
    return Project.model_validate(db_project)


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: UUID, db: DBSession) -> Project:
    """Get a project by ID."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))
    return Project.model_validate(project)


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: UUID,
    update: ProjectUpdate,
    db: DBSession,
) -> Project:
    """Update a project."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return Project.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db: DBSession) -> None:
    """Delete a project."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))

    await db.delete(project)
