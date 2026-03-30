"""Shared fixtures for ISO docs tests."""

from uuid import UUID

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        select(UserDB).where(UserDB.id == DEBUG_USER_ID)
    )
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEBUG_USER_ID, email="dev@test.com"))
        await db_session.flush()
