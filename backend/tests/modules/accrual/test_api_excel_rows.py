"""HTTP tests for /api/accrual/excel-rows."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB, DriftKind
from app.modules.accrual.models.accrual_excel_row import AccrualExcelRowDB
from app.modules.accrual.models.accrual_import_run import AccrualImportRunDB

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    if not (
        await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    ).scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _seed_run(
    db: AsyncSession,
    *,
    completed: bool = True,
    started_at: datetime | None = None,
) -> AccrualImportRunDB:
    now = datetime.now(UTC)
    run = AccrualImportRunDB(
        id=uuid4(),
        source_path="/tmp/test.xlsx",
        started_at=started_at or now,
        completed_at=now if completed else None,
    )
    db.add(run)
    await db.flush()
    return run


async def _seed_row(
    db: AsyncSession,
    *,
    run_id: UUID,
    position: int,
    excel_code: str,
    value_eur: Decimal = Decimal("1000.00"),
) -> AccrualExcelRowDB:
    row = AccrualExcelRowDB(
        import_run_id=run_id,
        import_run_position=position,
        excel_code=excel_code,
        value_eur=value_eur,
        monthly_cells=[],
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_list_excel_rows_defaults_to_latest_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import timedelta

    base = datetime.now(UTC) - timedelta(hours=1)
    older = await _seed_run(db_session, started_at=base)
    await _seed_row(db_session, run_id=older.id, position=0, excel_code="OLD.1")
    newer = await _seed_run(db_session, started_at=base + timedelta(minutes=30))
    await _seed_row(db_session, run_id=newer.id, position=0, excel_code="NEW.1")
    await db_session.commit()

    resp = await client.get("/api/accrual/excel-rows")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["excel_code"] == "NEW.1"
    assert data["import_run_id"] == str(newer.id)


@pytest.mark.asyncio
async def test_list_excel_rows_returns_empty_when_no_runs(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/excel-rows")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["import_run_id"] is None


@pytest.mark.asyncio
async def test_list_excel_rows_filters_by_code_ilike(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    run = await _seed_run(db_session)
    await _seed_row(db_session, run_id=run.id, position=0, excel_code="ALPHA.X")
    await _seed_row(db_session, run_id=run.id, position=1, excel_code="BETA.Y")
    await db_session.commit()

    resp = await client.get("/api/accrual/excel-rows", params={"excel_code": "alpha"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["excel_code"] == "ALPHA.X"


@pytest.mark.asyncio
async def test_list_excel_rows_unmatched_only_filters_via_drift(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    run = await _seed_run(db_session)
    await _seed_row(db_session, run_id=run.id, position=0, excel_code="MATCHED.1")
    await _seed_row(db_session, run_id=run.id, position=1, excel_code="UNMATCHED.1")
    # Drift finding for the unmatched code only.
    db_session.add(
        AccrualDriftFindingDB(
            kind=DriftKind.MISSING_TRACKER.value,
            project_id=None,
            excel_code="UNMATCHED.1",
            import_run_id=run.id,
            payload={},
        )
    )
    await db_session.commit()

    resp = await client.get("/api/accrual/excel-rows", params={"unmatched_only": "true"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["excel_code"] == "UNMATCHED.1"


@pytest.mark.asyncio
async def test_list_runs_returns_recent_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import timedelta

    base = datetime.now(UTC) - timedelta(hours=1)
    await _seed_run(db_session, started_at=base)
    await _seed_run(db_session, completed=False, started_at=base + timedelta(minutes=30))
    await db_session.commit()

    resp = await client.get("/api/accrual/excel-rows/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 2
    # In-flight runs (no completed_at) come first when more recent.
    assert runs[0]["completed_at"] is None
    assert runs[1]["completed_at"] is not None
