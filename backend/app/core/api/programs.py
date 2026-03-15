"""Programs endpoints."""

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.api.deps import AdminUser, CurrentUser, DBSession, limiter
from app.core.models.program import Program, ProgramCreate, ProgramDB

router = APIRouter()


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
    request: Request, current_user: AdminUser, db: DBSession, payload: ProgramCreate
) -> Program:
    program = ProgramDB(name=payload.name)
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return Program.model_validate(program)
