"""API dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig, get_scoring_config
from app.core.auth import TokenData, get_current_user
from app.database import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]
ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
