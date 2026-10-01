"""Programs endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, exists, select

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.auth import TokenData
from app.core.models.program import Program, ProgramCreate, ProgramDB, ProgramUpdate
from app.core.models.project import ProjectDB
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
async def update_program(
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
    if payload.name is not None:
        clash = (
            await db.execute(
                select(ProgramDB.id).where(
                    ProgramDB.name == payload.name, ProgramDB.id != program_id
                )
            )
        ).first()
        if clash is not None:
            raise HTTPException(status_code=409, detail="A program with this name already exists")
        program.name = payload.name
    if payload.is_internal is not None:
        program.is_internal = payload.is_internal
    await db.flush()
    await db.refresh(program)
    logger.info(
        "program_updated",
        program_id=str(program_id),
        name=program.name,
        is_internal=program.is_internal,
        fields=sorted(payload.model_dump(exclude_none=True)),
        user_id=current_user.user_id,
    )
    return Program.model_validate(program)


@router.delete(
    "/{program_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Missing portfolio:manage permission"},
        404: {"description": "Program not found"},
        409: {"description": "Program still has projects attached"},
    },
)
@limiter.limit("30/minute")
async def delete_program(
    request: Request,
    program_id: UUID,
    current_user: PortfolioManager,
    db: DBSession,
) -> None:
    program = (
        await db.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    ).scalar_one_or_none()
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    # projects.program_id is ON DELETE SET NULL: deleting would silently orphan contracts.
    has_projects = await db.scalar(select(exists().where(ProjectDB.program_id == program_id)))
    if has_projects:
        raise HTTPException(
            status_code=409, detail="Program has projects attached; reassign them first"
        )
    # Core DELETE so the DB cascades profile, terms and links.
    await db.execute(delete(ProgramDB).where(ProgramDB.id == program_id))
    logger.info(
        "program_deleted",
        program_id=str(program_id),
        name=program.name,
        user_id=current_user.user_id,
    )
