"""Programs endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.auth import TokenData
from app.core.models.program import Program, ProgramCreate, ProgramDB, ProgramUpdate
from app.core.permissions import Action, require_permission

ProjectManager = Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]
PortfolioManager = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_MANAGE))]

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


@router.patch(
    "/{program_id}",
    responses={
        404: {"description": "Program not found"},
        409: {"description": "Duplicate program name"},
    },
)
@limiter.limit("30/minute")
async def rename_program(
    request: Request,
    program_id: UUID,
    payload: ProgramUpdate,
    current_user: PortfolioManager,
    db: DBSession,
) -> Program:
    program = (
        await db.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    ).scalar_one_or_none()
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    clash = (
        await db.execute(
            select(ProgramDB.id).where(ProgramDB.name == payload.name, ProgramDB.id != program_id)
        )
    ).first()
    if clash is not None:
        raise HTTPException(status_code=409, detail="A program with this name already exists")
    program.name = payload.name
    await db.flush()
    await db.refresh(program)
    logger.info(
        "program_renamed",
        program_id=str(program_id),
        name=program.name,
        user_id=current_user.user_id,
    )
    return Program.model_validate(program)
