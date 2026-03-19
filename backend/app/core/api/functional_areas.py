"""Functional areas listing endpoint."""

from fastapi import APIRouter
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.functional_area import FunctionalArea, FunctionalAreaDB

router = APIRouter()


@router.get("")
async def list_functional_areas(
    db: DBSession,
    user: CurrentUser,
) -> list[FunctionalArea]:
    stmt = select(FunctionalAreaDB).order_by(FunctionalAreaDB.name)
    result = await db.execute(stmt)
    return [FunctionalArea.model_validate(fa) for fa in result.scalars().all()]
