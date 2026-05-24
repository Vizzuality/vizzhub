"""HTTP tests for /api/accrual/drift."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB, DriftKind

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Seed the synthetic dev user so resolved_by FK doesn't fire."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _seed_finding(
    db: AsyncSession,
    *,
    kind: DriftKind = DriftKind.DATE_EXTEND,
    project_id: UUID | None = None,
    excel_code: str | None = "ABC.123",
    resolved: bool = False,
    payload: dict | None = None,
) -> AccrualDriftFindingDB:
    finding = AccrualDriftFindingDB(
        id=uuid4(),
        kind=kind.value,
        project_id=project_id,
        excel_code=excel_code,
        payload=payload or {},
        resolved_at=datetime.now(UTC) if resolved else None,
        resolution="seeded" if resolved else None,
    )
    db.add(finding)
    await db.flush()
    return finding


async def _seed_project(db: AsyncSession, *, code: str = "ABC.123") -> ProjectDB:
    p = ProjectDB(
        name=f"Project {code}",
        code=code,
        currency="USD",
        is_billable=True,
        status="live",
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_list_drift_findings_returns_paginated_with_total(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    for _ in range(3):
        await _seed_finding(db_session)
    await db_session.commit()

    resp = await client.get("/api/accrual/drift")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Unresolved should come first by default.
    assert all(item["resolved_at"] is None for item in data["items"])


@pytest.mark.asyncio
async def test_list_drift_findings_filters_by_kind(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_finding(db_session, kind=DriftKind.DATE_EXTEND)
    await _seed_finding(db_session, kind=DriftKind.STATUS_STALE)
    await _seed_finding(db_session, kind=DriftKind.MISSING_TRACKER)
    await db_session.commit()

    resp = await client.get("/api/accrual/drift", params={"kind": "date_extend"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["kind"] == "date_extend"


@pytest.mark.asyncio
async def test_list_drift_findings_rejects_invalid_kind(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/accrual/drift", params={"kind": "not_a_real_kind"})
    assert resp.status_code == 400
    assert "Invalid kind" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_drift_findings_includes_project_info_when_joined(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    project = await _seed_project(db_session)
    await _seed_finding(db_session, project_id=project.id, excel_code=project.code)
    await db_session.commit()

    resp = await client.get("/api/accrual/drift")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["project_id"] == str(project.id)
    assert item["project_name"] == project.name
    assert item["project_code"] == project.code


@pytest.mark.asyncio
async def test_list_drift_findings_resolved_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_finding(db_session, resolved=False)
    await _seed_finding(db_session, resolved=True)
    await db_session.commit()

    open_only = await client.get("/api/accrual/drift", params={"resolved": "false"})
    assert open_only.json()["total"] == 1
    assert open_only.json()["items"][0]["resolved_at"] is None

    resolved_only = await client.get("/api/accrual/drift", params={"resolved": "true"})
    assert resolved_only.json()["total"] == 1
    assert resolved_only.json()["items"][0]["resolved_at"] is not None


@pytest.mark.asyncio
async def test_drift_summary_groups_by_kind_and_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_finding(db_session, kind=DriftKind.DATE_EXTEND, resolved=False)
    await _seed_finding(db_session, kind=DriftKind.DATE_EXTEND, resolved=True)
    await _seed_finding(db_session, kind=DriftKind.STATUS_STALE, resolved=False)
    await db_session.commit()

    resp = await client.get("/api/accrual/drift/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_open"] == 2
    assert data["total_resolved"] == 1
    assert data["by_kind"]["date_extend"] == {"open": 1, "resolved": 1}
    assert data["by_kind"]["status_stale"] == {"open": 1, "resolved": 0}


@pytest.mark.asyncio
async def test_resolve_drift_finding_sets_resolution_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    finding = await _seed_finding(db_session)
    await db_session.commit()

    resp = await client.post(
        f"/api/accrual/drift/{finding.id}/resolve",
        json={"resolution": "Applied Excel dates to tracker"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution"] == "Applied Excel dates to tracker"
    assert data["resolved_at"] is not None
    assert data["resolved_by"] == str(_DEV_USER_ID)


@pytest.mark.asyncio
async def test_resolve_drift_finding_404_when_missing(client: AsyncClient) -> None:
    resp = await client.post(f"/api/accrual/drift/{uuid4()}/resolve", json={"resolution": "n/a"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_drift_finding_rejects_empty_resolution(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    finding = await _seed_finding(db_session)
    await db_session.commit()

    resp = await client.post(f"/api/accrual/drift/{finding.id}/resolve", json={"resolution": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reopen_drift_finding_clears_resolution(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    finding = await _seed_finding(db_session, resolved=True)
    await db_session.commit()

    resp = await client.post(f"/api/accrual/drift/{finding.id}/reopen")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_at"] is None
    assert data["resolution"] is None
    assert data["resolved_by"] is None
