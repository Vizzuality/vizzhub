"""API dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig, get_scoring_config
from app.core.auth import TokenData, get_current_user, require_role
from app.core.exceptions import ProjectNotFoundError
from app.database import get_db
from app.core.models.project import ProjectDB
from app.services.score_cache import ScoreCacheService

# Shared rate limiter instance
limiter = Limiter(key_func=get_remote_address)

DBSession = Annotated[AsyncSession, Depends(get_db)]
ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
AdminUser = Annotated[TokenData, Depends(require_role("admin"))]


def get_score_cache(request: Request) -> ScoreCacheService | None:
    """Get score cache from app state (None if Redis unavailable)."""
    return getattr(request.app.state, "score_cache", None)


OptionalScoreCache = Annotated[ScoreCacheService | None, Depends(get_score_cache)]


async def get_project_or_404(db: AsyncSession, project_id: UUID) -> ProjectDB:
    """
    Fetch a project by ID or raise 404 if not found.

    Args:
        db: Database session
        project_id: Project UUID

    Returns:
        ProjectDB: The project if found

    Raises:
        ProjectNotFoundError: If project doesn't exist
    """
    result = await db.execute(select(ProjectDB).where(ProjectDB.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))
    return project
