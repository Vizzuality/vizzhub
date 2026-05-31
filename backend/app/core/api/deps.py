"""API dependencies."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig, get_scoring_config
from app.core.auth import TokenData, get_current_user
from app.core.exceptions import ProjectNotFoundError
from app.core.models.project import ProjectDB
from app.core.permissions import Action, require_permission
from app.database import get_db
from app.modules.scorecard.services.score_cache import ScoreCacheService

# Shared rate limiter instance
limiter = Limiter(key_func=get_remote_address)

DBSession = Annotated[AsyncSession, Depends(get_db)]
ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
AdminUser = Annotated[TokenData, Depends(require_permission(Action.ALL))]
ProjectManager = Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]


def get_score_cache(request: Request) -> ScoreCacheService | None:
    """Get score cache from app state (None if Redis unavailable)."""
    return getattr(request.app.state, "score_cache", None)


OptionalScoreCache = Annotated[ScoreCacheService | None, Depends(get_score_cache)]


async def get_project_or_404(db: AsyncSession, project_id: UUID) -> ProjectDB:
    """Fetch a project by ID or raise ``ProjectNotFoundError`` (→ 404)."""
    result = await db.execute(select(ProjectDB).where(ProjectDB.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))
    return project


async def get_or_404(
    db: AsyncSession,
    model: Any,
    entity_id: Any,
    detail: str = "Not found",
) -> Any:
    """Generic primary-key lookup that raises HTTP 404 on miss.

    Use for simple read-then-or-fail flows; for project lookups prefer
    ``get_project_or_404`` which surfaces a typed exception.
    """
    entity = await db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return entity
