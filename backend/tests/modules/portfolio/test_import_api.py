import io
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.user import UserDB
from app.database import get_db
from app.main import app

_MANAGER_ID = UUID("00000000-0000-0000-0000-000000000042")

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _manager() -> TokenData:
    return TokenData(
        user_id=str(_MANAGER_ID),
        email="m@test.com",
        roles=["manager"],
        permissions=["portfolio:view", "portfolio:manage"],
    )


@pytest_asyncio.fixture
async def manager_client(db_session: AsyncSession) -> AsyncClient:
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _manager
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Categorised"
    ws.append(["stray"])
    header = [None] * 21
    header[2] = "Name"
    ws.append(header)
    r = [None] * 21
    r[2] = "Brand New Project"
    r[7] = "Tools"
    ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_matches_apply_flow(
    manager_client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.core.models.project import ProjectDB
    from app.core.models.taxonomy import TaxonomyDB, TaxonomyTermDB

    db_session.add(UserDB(id=_MANAGER_ID, email="m@test.com"))
    tax = TaxonomyDB(slug="service", name="Service", cardinality="multi", allows_primary=True)
    proj = ProjectDB(name="Brand New Project", is_billable=True, is_absence=False, status="live")
    db_session.add_all([tax, proj])
    await db_session.flush()
    db_session.add(TaxonomyTermDB(taxonomy_id=tax.id, slug="tools", name="Tools"))
    await db_session.commit()

    up = await manager_client.post(
        "/api/portfolio/import/upload",
        files={
            "file": ("overview.xlsx", _xlsx_bytes(), _XLSX)
        },  # _xlsx_bytes name row = "Brand New Project"
    )
    assert up.status_code == 200
    batch = up.json()["batch_id"]

    matches = await manager_client.get(f"/api/portfolio/import/{batch}/matches")
    assert matches.status_code == 200
    body = matches.json()
    assert body[0]["suggested_project"]["project_id"] == str(proj.id)
    sid = body[0]["staging_id"]

    apply = await manager_client.post(
        f"/api/portfolio/import/{batch}/apply",
        json=[{"staging_id": sid, "project_id": str(proj.id), "program_action": "create"}],
    )
    assert apply.status_code == 200
    assert apply.json()["programs_created"] == 1


@pytest.mark.asyncio
async def test_upload_forbidden_for_viewer(client: AsyncClient) -> None:
    async def _viewer() -> TokenData:
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000010",
            email="v@test.com",
            roles=["user"],
            permissions=["portfolio:view"],
        )

    app.dependency_overrides[get_current_user] = _viewer
    try:
        resp = await client.post(
            "/api/portfolio/import/upload",
            files={"file": ("o.xlsx", _xlsx_bytes(), _XLSX)},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
