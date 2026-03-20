"""Tests for invoice CRUD and status transitions."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def setup_invoices(db_session: AsyncSession) -> dict:
    user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    return {"project_id": str(project.id)}


@pytest.mark.asyncio
class TestInvoices:
    async def test_list_empty(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_invoice(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 5000,
                "code": "INV-001",
                "due_date": "2026-06-01",
                "milestone": "Milestone 1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 5000.0
        assert data["status"] == "scheduled"
        assert data["milestone"] == "Milestone 1"

    async def test_update_invoice(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 5000,
                "code": "INV-001",
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        resp = await client.put(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}",
            json={"amount": 7500, "milestone": "M1 updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["amount"] == 7500.0
        assert resp.json()["milestone"] == "M1 updated"

    async def test_auto_pending_by_date(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        """Scheduled invoices with past due_date show as pending_to_issue."""
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2020-01-01",
                "milestone": "M1",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending_to_issue"

    async def test_scheduled_stays_for_future_date(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2030-06-01",
                "milestone": "M1",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "scheduled"

    async def test_full_lifecycle(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        """Past due_date auto-promotes to pending, then manual transitions."""
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2020-01-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]
        assert resp.json()["status"] == "pending_to_issue"

        for status in ("waiting_for_payment", "paid"):
            resp = await client.post(
                f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
                json={"status": status},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_invalid_transition_from_scheduled(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        """Scheduled with future date cannot be manually transitioned."""
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2030-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "paid"},
        )
        assert resp.status_code == 400

    async def test_reverse_transition_paid_to_waiting(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2020-01-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        # Forward to paid
        for status in ("waiting_for_payment", "paid"):
            await client.post(
                f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
                json={"status": status},
            )
        # Reverse to waiting
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "waiting_for_payment"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "waiting_for_payment"

    async def test_delete_invoice(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-001",
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        resp = await client.delete(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}",
        )
        assert resp.status_code == 204

        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert resp.json() == []

    async def test_list_ordered_by_due_date(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        # Create in reverse order
        await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={"code": "INV-002", "amount": 2000, "due_date": "2026-12-01", "milestone": "M2"},
        )
        await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={"code": "INV-001", "amount": 1000, "due_date": "2026-06-01", "milestone": "M1"},
        )

        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["due_date"] == "2026-06-01"
        assert data[1]["due_date"] == "2026-12-01"
