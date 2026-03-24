"""Project tracker settings endpoints (contract rate)."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]

from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB

router = APIRouter()


class ProjectSettingsUpdate(BaseModel):
    contract_rate: float = Field(gt=0)


class ProjectSettingsResponse(BaseModel):
    project_id: str
    contract_rate: float


@router.get("/{project_id}/settings")
async def get_project_settings(
    project_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> ProjectSettingsResponse:
    result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == project_id
        )
    )
    settings = result.scalar_one_or_none()
    return ProjectSettingsResponse(
        project_id=str(project_id),
        contract_rate=float(settings.contract_rate) if settings else 175.0,
    )


@router.put("/{project_id}/settings")
async def update_project_settings(
    project_id: UUID,
    body: ProjectSettingsUpdate,
    db: DBSession,
    user: TrackerManager,
) -> ProjectSettingsResponse:
    result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == project_id
        )
    )
    settings = result.scalar_one_or_none()

    if settings:
        settings.contract_rate = Decimal(str(body.contract_rate))
    else:
        settings = TrackerProjectSettingsDB(
            project_id=project_id,
            contract_rate=Decimal(str(body.contract_rate)),
        )
        db.add(settings)

    await db.commit()
    await db.refresh(settings)

    return ProjectSettingsResponse(
        project_id=str(project_id),
        contract_rate=float(settings.contract_rate),
    )
