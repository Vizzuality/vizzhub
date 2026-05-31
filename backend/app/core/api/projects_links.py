"""Project links endpoints (/api/projects/{project_id}/links)."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from app.core.api.deps import (
    CurrentUser,
    DBSession,
    ProjectManager,
    get_project_or_404,
    limiter,
)
from app.core.models.link import Link, LinkDB

router = APIRouter()


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
