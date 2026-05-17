"""Available currencies endpoint."""

from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.exchange_rate_service import get_available_currencies

router = APIRouter()


@router.get("")
async def list_currencies(db: DBSession, user: CurrentUser) -> list[str]:
    """Return all currency codes with at least one ECB rate stored (plus EUR)."""
    return await get_available_currencies(db)
