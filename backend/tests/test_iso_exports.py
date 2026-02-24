"""Tests for ISO export API endpoints."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

from app.models.user import UserDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _ensure_dev_user(db_session) -> None:
    from sqlalchemy import select

    result = await db_session.execute(
        select(UserDB).where(UserDB.id == DEV_USER_ID)
    )
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _make_snapshot(db_session, captured_at=None) -> AccessSnapshotDB:
    snapshot = AccessSnapshotDB(
        provider="google_workspace",
        captured_at=captured_at or datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
        data_version="1",
        source_metadata={"domain": "test.com"},
        data={
            "users": [
                {
                    "id": "u1",
                    "name": "Alice",
                    "email": "alice@test.com",
                    "suspended": False,
                    "org_unit_path": "/",
                }
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        },
        summary={
            "total_users": 1,
            "total_admins": 0,
            "total_groups": 0,
            "external_members": 0,
        },
    )
    db_session.add(snapshot)
    await db_session.flush()
    return snapshot


async def _make_review(db_session, snapshot_id, status="draft") -> AccessReviewDB:
    review = AccessReviewDB(
        snapshot_id=snapshot_id,
        status=status,
        scope="All users and groups",
    )
    db_session.add(review)
    await db_session.flush()
    return review


class TestExportSnapshotRange:
    @pytest.mark.asyncio
    async def test_export_date_range(
        self, client: AsyncClient, db_session
    ) -> None:
        await _ensure_dev_user(db_session)
        await _make_snapshot(
            db_session,
            captured_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        await _make_snapshot(
            db_session,
            captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-12-31"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == XLSX_CONTENT_TYPE

        wb = load_workbook(BytesIO(response.content))
        assert "Summary" in wb.sheetnames
        assert len(wb.sheetnames) == 3

    @pytest.mark.asyncio
    async def test_export_empty_range_returns_empty_summary(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-12-31"},
        )
        assert response.status_code == 200
        wb = load_workbook(BytesIO(response.content))
        assert len(wb.sheetnames) == 1
        assert wb.sheetnames[0] == "Summary"

    @pytest.mark.asyncio
    async def test_export_invalid_date_format(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "bad-date", "to": "2026-12-31"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_export_to_before_from_returns_400(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-12-31", "to": "2026-01-01"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_export_filters_by_date_range(
        self, client: AsyncClient, db_session
    ) -> None:
        await _ensure_dev_user(db_session)
        await _make_snapshot(
            db_session,
            captured_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        await _make_snapshot(
            db_session,
            captured_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )

        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-06-30"},
        )
        assert response.status_code == 200
        wb = load_workbook(BytesIO(response.content))
        assert len(wb.sheetnames) == 2

    @pytest.mark.asyncio
    async def test_export_has_content_disposition_header(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-12-31"},
        )
        assert response.status_code == 200
        assert "content-disposition" in response.headers
        assert "iso_access_review_2026-01-01_2026-12-31.xlsx" in response.headers[
            "content-disposition"
        ]


class TestExportSingleSnapshot:
    @pytest.mark.asyncio
    async def test_export_single_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        await _ensure_dev_user(db_session)
        snapshot = await _make_snapshot(db_session)

        response = await client.get(
            f"/api/iso/exports/snapshots/{snapshot.id}",
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == XLSX_CONTENT_TYPE

        wb = load_workbook(BytesIO(response.content))
        assert len(wb.sheetnames) == 2

    @pytest.mark.asyncio
    async def test_export_snapshot_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.get(f"/api/iso/exports/snapshots/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_single_has_content_disposition(
        self, client: AsyncClient, db_session
    ) -> None:
        await _ensure_dev_user(db_session)
        snapshot = await _make_snapshot(
            db_session,
            captured_at=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
        )

        response = await client.get(
            f"/api/iso/exports/snapshots/{snapshot.id}",
        )
        assert response.status_code == 200
        assert "iso_access_review_2026-06-15.xlsx" in response.headers[
            "content-disposition"
        ]

    @pytest.mark.asyncio
    async def test_export_snapshot_with_review_and_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        await _ensure_dev_user(db_session)
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id, status="signed")
        action = AccessReviewActionDB(
            review_id=review.id,
            subject_type="user",
            subject_id="u1",
            subject_label="Alice",
            change_type="new_user",
            action_taken="accepted",
            justification="Approved",
        )
        db_session.add(action)
        await db_session.flush()

        response = await client.get(
            f"/api/iso/exports/snapshots/{snapshot.id}",
        )
        assert response.status_code == 200

        wb = load_workbook(BytesIO(response.content))
        tab_name = [s for s in wb.sheetnames if s != "Summary"][0]
        ws = wb[tab_name]

        all_values = [
            ws.cell(row=r, column=c).value
            for r in range(1, ws.max_row + 1)
            for c in range(1, ws.max_column + 1)
        ]
        assert "Approved" in all_values
        assert "alice@test.com" in all_values
