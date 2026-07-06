"""Tests for program rename (F2)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.program import ProgramDB
from app.database import get_db
from app.main import app


def _token(*permissions: str) -> TokenData:
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000042",
        email="t@test.com",
        roles=["user"],
        permissions=list(permissions),
    )


@pytest_asyncio.fixture
async def manager(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> TokenData:
        return _token("portfolio:manage")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rename_program(manager: AsyncClient, db_session: AsyncSession) -> None:
    prog = ProgramDB(name="Old Name")
    db_session.add(prog)
    await db_session.commit()
    resp = await manager.patch(f"/api/programs/{prog.id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_rename_program_409_on_duplicate(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    a = ProgramDB(name="Taken")
    b = ProgramDB(name="Renamable")
    db_session.add_all([a, b])
    await db_session.commit()
    resp = await manager.patch(f"/api/programs/{b.id}", json={"name": "Taken"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_rename_program_404_unknown(manager: AsyncClient) -> None:
    resp = await manager.patch(
        "/api/programs/00000000-0000-0000-0000-000000000001", json={"name": "X"}
    )
    assert resp.status_code == 404
