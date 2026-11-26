"""Copper opportunities offered for import into the new-project form."""

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.core.api.deps import DBSession, ProjectCreator, limiter
from app.core.services.copper_client import CopperAuthError, CopperClient, CopperError
from app.core.services.copper_opportunities import list_importable_opportunities

logger = structlog.get_logger()

router = APIRouter()


class _FromAttributes(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectRefOut(_FromAttributes):
    id: UUID
    name: str


class NewClientOut(_FromAttributes):
    name: str
    code: str | None
    copper_company_id: int | None


class CopperOpportunityOut(_FromAttributes):
    opportunity_id: int
    name: str
    group: Literal["pending_signature", "signed"]
    stage_changed_on: date | None
    company_name: str | None
    code: str | None
    currency: str | None
    original_budget: float | None
    start_date: date | None
    end_date: date | None
    client_id: UUID | None
    client_name: str | None
    new_client: NewClientOut | None
    linked_projects: list[ProjectRefOut]
    suggestion: ProjectRefOut | None


@router.get(
    "/copper-opportunities",
    responses={
        409: {"description": "Copper is not connected"},
        502: {"description": "Copper could not be read"},
    },
)
@limiter.limit("30/minute")
async def list_copper_opportunities(
    request: Request, current_user: ProjectCreator, db: DBSession
) -> list[CopperOpportunityOut]:
    """Open deals in Happy to Proceed plus recently signed deals without a project."""
    copper = await CopperClient.from_db(db)
    if copper is None:
        raise HTTPException(status_code=409, detail="Copper is not connected")
    try:
        async with copper:
            opportunities = await list_importable_opportunities(db, copper, now=datetime.now(UTC))
    except CopperAuthError as exc:
        logger.warning("copper_opportunities_failed", user_id=current_user.user_id, auth=True)
        raise HTTPException(
            status_code=502,
            detail="Copper rejected the saved API key. Update it in Admin → Integrations → Copper.",
        ) from exc
    except CopperError as exc:
        logger.warning("copper_opportunities_failed", user_id=current_user.user_id)
        raise HTTPException(
            status_code=502, detail="Could not read opportunities from Copper. Try again later."
        ) from exc
    return [CopperOpportunityOut.model_validate(o) for o in opportunities]
