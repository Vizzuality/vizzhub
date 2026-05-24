"""HTTP tests for /api/accrual/aliases."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_alias import AccrualAliasDB

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Seed the synthetic dev user so created_by FK doesn't fire."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _seed_project(db: AsyncSession, *, code: str) -> ProjectDB:
    p = ProjectDB(
        name=f"Project {code}", code=code, currency="USD", is_billable=True, status="live"
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_create_alias_returns_201_and_serializes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project = await _seed_project(db_session, code="WCRC.LCE.2")
    await db_session.commit()

    resp = await client.post(
        "/api/accrual/aliases",
        json={
            "excel_code": "WRCR.LCE.2",
            "project_id": str(project.id),
            "weight": "1.0",
            "notes": "letter-swap typo, manual fix",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["excel_code"] == "WRCR.LCE.2"
    assert data["project_id"] == str(project.id)
    assert Decimal(data["weight"]) == Decimal("1.0")
    assert data["created_by"] == str(_DEV_USER_ID)


@pytest.mark.asyncio
async def test_create_alias_404_when_project_missing(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/accrual/aliases",
        json={"excel_code": "X.Y", "project_id": str(uuid4()), "weight": "1.0"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_alias_409_on_duplicate(client: AsyncClient, db_session: AsyncSession) -> None:
    project = await _seed_project(db_session, code="A.1")
    await db_session.commit()
    body = {"excel_code": "X.Y", "project_id": str(project.id), "weight": "1.0"}
    first = await client.post("/api/accrual/aliases", json=body)
    assert first.status_code == 201
    second = await client.post("/api/accrual/aliases", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_alias_rejects_weight_above_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project = await _seed_project(db_session, code="A.2")
    await db_session.commit()
    resp = await client.post(
        "/api/accrual/aliases",
        json={"excel_code": "X.Y", "project_id": str(project.id), "weight": "1.5"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_aliases_returns_joined_project_info(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project = await _seed_project(db_session, code="LIST.PR1")
    db_session.add(
        AccrualAliasDB(
            excel_code="LIST.EXCEL1",
            project_id=project.id,
            weight=Decimal("1.0"),
        )
    )
    await db_session.commit()

    resp = await client.get("/api/accrual/aliases")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["project_name"] == project.name
    assert items[0]["project_code"] == project.code


@pytest.mark.asyncio
async def test_list_aliases_filters_by_excel_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    p1 = await _seed_project(db_session, code="F.PR1")
    p2 = await _seed_project(db_session, code="F.PR2")
    db_session.add(AccrualAliasDB(excel_code="F.EX1", project_id=p1.id, weight=Decimal("1.0")))
    db_session.add(AccrualAliasDB(excel_code="F.EX2", project_id=p2.id, weight=Decimal("1.0")))
    await db_session.commit()

    resp = await client.get("/api/accrual/aliases", params={"excel_code": "F.EX2"})
    items = resp.json()
    assert len(items) == 1
    assert items[0]["excel_code"] == "F.EX2"


@pytest.mark.asyncio
async def test_update_alias_changes_weight_and_notes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project = await _seed_project(db_session, code="U.PR1")
    alias = AccrualAliasDB(excel_code="U.EX1", project_id=project.id, weight=Decimal("1.0"))
    db_session.add(alias)
    await db_session.commit()

    resp = await client.patch(
        f"/api/accrual/aliases/{alias.id}",
        json={"weight": "0.6", "notes": "split"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["weight"]) == Decimal("0.6")
    assert data["notes"] == "split"


@pytest.mark.asyncio
async def test_update_alias_404_when_missing(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/accrual/aliases/{uuid4()}", json={"weight": "0.5"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_alias_204_and_gone(client: AsyncClient, db_session: AsyncSession) -> None:
    project = await _seed_project(db_session, code="D.PR1")
    alias = AccrualAliasDB(excel_code="D.EX1", project_id=project.id, weight=Decimal("1.0"))
    db_session.add(alias)
    await db_session.commit()

    resp = await client.delete(f"/api/accrual/aliases/{alias.id}")
    assert resp.status_code == 204

    resp2 = await client.delete(f"/api/accrual/aliases/{alias.id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_bulk_create_aliases_one_excel_to_many_projects(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    p1 = await _seed_project(db_session, code="BULK.A")
    p2 = await _seed_project(db_session, code="BULK.B")
    await db_session.commit()

    resp = await client.post(
        "/api/accrual/aliases/bulk",
        json={
            "excel_code": "BULK.EXCEL",
            "mappings": [
                {"project_id": str(p1.id), "weight": "0.6"},
                {"project_id": str(p2.id), "weight": "0.4"},
            ],
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert len(created) == 2
    weights = sorted(Decimal(c["weight"]) for c in created)
    assert weights == [Decimal("0.4"), Decimal("0.6")]


@pytest.mark.asyncio
async def test_bulk_create_with_replace_existing_clears_prior(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    p1 = await _seed_project(db_session, code="R.PR1")
    p2 = await _seed_project(db_session, code="R.PR2")
    p3 = await _seed_project(db_session, code="R.PR3")
    # Seed prior alias to p1.
    db_session.add(AccrualAliasDB(excel_code="R.EXCEL", project_id=p1.id, weight=Decimal("1.0")))
    await db_session.commit()

    resp = await client.post(
        "/api/accrual/aliases/bulk",
        json={
            "excel_code": "R.EXCEL",
            "mappings": [
                {"project_id": str(p2.id), "weight": "0.5"},
                {"project_id": str(p3.id), "weight": "0.5"},
            ],
            "replace_existing": True,
        },
    )
    assert resp.status_code == 201
    listing = await client.get("/api/accrual/aliases", params={"excel_code": "R.EXCEL"})
    project_ids = {item["project_id"] for item in listing.json()}
    assert project_ids == {str(p2.id), str(p3.id)}


@pytest.mark.asyncio
async def test_bulk_create_404_when_one_project_missing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    p1 = await _seed_project(db_session, code="MISS.A")
    await db_session.commit()

    resp = await client.post(
        "/api/accrual/aliases/bulk",
        json={
            "excel_code": "MISS.EXCEL",
            "mappings": [
                {"project_id": str(p1.id), "weight": "0.5"},
                {"project_id": str(uuid4()), "weight": "0.5"},
            ],
        },
    )
    assert resp.status_code == 404
    # Verify nothing was persisted on failure (atomic).
    listing = await client.get("/api/accrual/aliases", params={"excel_code": "MISS.EXCEL"})
    assert listing.json() == []
