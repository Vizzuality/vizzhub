"""Tests for program rename (F2)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
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


@pytest_asyncio.fixture
async def viewer(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> TokenData:
        return _token("portfolio:view")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_program_without_projects_cascades_profile_and_terms(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    prog = ProgramDB(name="Empty Program")
    db_session.add(prog)
    await db_session.flush()
    tax = TaxonomyDB(slug="topics", name="Topics", cardinality=Cardinality.MULTI)
    db_session.add(tax)
    await db_session.flush()
    term = TaxonomyTermDB(taxonomy_id=tax.id, slug="oceans", name="Oceans")
    db_session.add(term)
    await db_session.flush()
    db_session.add(PortfolioProfileDB(program_id=prog.id, stage="Active"))
    db_session.add(EntityTermDB(term_id=term.id, taxonomy_id=tax.id, program_id=prog.id))
    await db_session.commit()
    prog_id = prog.id

    resp = await manager.delete(f"/api/programs/{prog_id}")
    assert resp.status_code == 204

    db_session.expire_all()
    assert await db_session.get(ProgramDB, prog_id) is None
    remaining = await db_session.scalar(
        select(func.count()).select_from(EntityTermDB).where(EntityTermDB.program_id == prog_id)
    )
    assert remaining == 0
    profile = await db_session.scalar(
        select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == prog_id)
    )
    assert profile is None


@pytest.mark.asyncio
async def test_delete_program_with_projects_returns_409(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    prog = ProgramDB(name="Busy Program")
    db_session.add(prog)
    await db_session.flush()
    db_session.add(
        ProjectDB(
            name="Busy 2026",
            status="finished",
            program_id=prog.id,
            is_billable=True,
            is_absence=False,
        )
    )
    await db_session.commit()
    prog_id = prog.id

    resp = await manager.delete(f"/api/programs/{prog_id}")
    assert resp.status_code == 409
    db_session.expire_all()
    assert await db_session.get(ProgramDB, prog_id) is not None


@pytest.mark.asyncio
async def test_delete_program_404_unknown(manager: AsyncClient) -> None:
    resp = await manager.delete("/api/programs/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_program_requires_manage_permission(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    prog = ProgramDB(name="Protected Program")
    db_session.add(prog)
    await db_session.commit()
    resp = await viewer.delete(f"/api/programs/{prog.id}")
    assert resp.status_code == 403
