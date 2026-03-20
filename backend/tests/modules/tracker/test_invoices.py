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
                "currency": "euro",
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

    async def test_transition_scheduled_to_pending(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "pending_to_issue"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_to_issue"

    async def test_full_lifecycle(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        for status in ("pending_to_issue", "waiting_for_payment", "paid"):
            resp = await client.post(
                f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
                json={"status": status},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_invalid_transition(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "paid"},
        )
        assert resp.status_code == 400

    async def test_reverse_transition(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "due_date": "2026-06-01",
                "milestone": "M1",
            },
        )
        inv_id = resp.json()["id"]

        # Forward to pending_to_issue
        await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "pending_to_issue"},
        )
        # Reverse back to scheduled
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/transition",
            json={"status": "scheduled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "scheduled"

    async def test_delete_invoice(
        self, client: AsyncClient, setup_invoices: dict,
    ) -> None:
        pid = setup_invoices["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
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
            json={"amount": 2000, "due_date": "2026-12-01", "milestone": "M2"},
        )
        await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={"amount": 1000, "due_date": "2026-06-01", "milestone": "M1"},
        )

        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["due_date"] == "2026-06-01"
        assert data[1]["due_date"] == "2026-12-01"
