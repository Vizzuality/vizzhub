"""Programs list endpoint."""

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.models.program import Program, ProgramDB

router = APIRouter()


@router.get("")
@limiter.limit("100/minute")
async def list_programs(
    request: Request, current_user: CurrentUser, db: DBSession
) -> list[Program]:
    result = await db.execute(select(ProgramDB).order_by(ProgramDB.name))
    return [Program.model_validate(p) for p in result.scalars().all()]
