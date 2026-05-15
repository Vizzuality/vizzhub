"""Programs endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.auth import TokenData
from app.core.models.program import Program, ProgramCreate, ProgramDB
from app.core.permissions import Action, require_permission

ProjectManager = Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]

router = APIRouter()
logger = structlog.get_logger()


@router.get("")
@limiter.limit("100/minute")
async def list_programs(
    request: Request, current_user: CurrentUser, db: DBSession
) -> list[Program]:
    result = await db.execute(select(ProgramDB).order_by(ProgramDB.name))
    return [Program.model_validate(p) for p in result.scalars().all()]


@router.post("")
@limiter.limit("30/minute")
async def create_program(
    request: Request, current_user: ProjectManager, db: DBSession, payload: ProgramCreate
) -> Program:
    program = ProgramDB(name=payload.name)
    db.add(program)
    await db.flush()
    await db.refresh(program)
    logger.info(
        "program_created",
        program_id=str(program.id),
        name=program.name,
        user_id=current_user.user_id,
    )
    return Program.model_validate(program)
