"""Tests for invoice postponement math and window boundaries.

Postpone rules (see app/modules/tracker/api/postponements.py):
- Only `pending_to_issue` invoices can be postponed.
- `base_date` = latest existing postponement date, else invoice.due_date.
- `window_base` = max(base_date, today)
- new date must be > base_date AND <= window_base + MAX_POSTPONE_DAYS (30).
- Paid / voided invoices cannot have their postponements deleted.
"""

from datetime import date, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def setup_pending_invoice(db_session: AsyncSession, client: AsyncClient) -> dict:
    user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    pid = str(project.id)

    past_due = (date.today() - timedelta(days=10)).isoformat()
    resp = await client.post(
        f"/api/tracker/projects/{pid}/invoices",
        json={
            "amount": 1000,
            "code": "INV-001",
            "due_date": past_due,
            "milestone": "M1",
        },
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    assert invoice["status"] == "pending_to_issue"
    return {"project_id": pid, "invoice_id": invoice["id"], "due_date": past_due}


@pytest.mark.asyncio
class TestPostponeWindow:
    async def test_postpone_rejected_when_invoice_scheduled(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        """Scheduled (future due) invoices cannot be postponed."""
        user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
        db_session.add(user)
        await db_session.flush()
        project = ProjectDB(name="Proj", status="live")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        pid = str(project.id)

        future = (date.today() + timedelta(days=60)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={"amount": 1000, "code": "INV-001", "due_date": future, "milestone": "M1"},
        )
        inv_id = resp.json()["id"]

        new_date = (date.today() + timedelta(days=90)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": new_date, "reason": "client delay"},
        )
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"].lower()

    async def test_postpone_within_30_days_succeeds(
        self, client: AsyncClient, setup_pending_invoice: dict,
    ) -> None:
        """First postpone: window_base = today (due_date is in the past)."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        new_date = (date.today() + timedelta(days=20)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": new_date, "reason": "client requested"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["postponed_to"] == new_date

    async def test_postpone_beyond_max_window_rejected(
        self, client: AsyncClient, setup_pending_invoice: dict,
    ) -> None:
        """Cannot postpone past window_base + 30 days."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        # window_base = today (due_date in past). 31 days from now must fail.
        too_far = (date.today() + timedelta(days=31)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": too_far, "reason": "anything"},
        )
        assert resp.status_code == 400
        assert "30 days" in resp.json()["detail"]

    async def test_postpone_must_be_after_base_date(
        self, client: AsyncClient, setup_pending_invoice: dict,
    ) -> None:
        """First postpone: new date must be > due_date."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]
        due_date = setup_pending_invoice["due_date"]

        # Same day as base_date -> rejected (must be strictly after).
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": due_date, "reason": "x"},
        )
        assert resp.status_code == 400
        assert "after" in resp.json()["detail"].lower()

    async def test_cannot_postpone_already_postponed_invoice(
        self, client: AsyncClient, setup_pending_invoice: dict,
    ) -> None:
        """Once postponed (latest > today), effective status is 'postponed' and a
        new postponement is blocked until the previous one expires."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        first = (date.today() + timedelta(days=10)).isoformat()
        r1 = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": first, "reason": "first"},
        )
        assert r1.status_code == 201, r1.text

        another = (date.today() + timedelta(days=20)).isoformat()
        r2 = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": another, "reason": "second"},
        )
        assert r2.status_code == 400
        assert "pending" in r2.json()["detail"].lower()

    async def test_delete_latest_postponement(
        self, client: AsyncClient, setup_pending_invoice: dict,
    ) -> None:
        """Removing the latest postponement is allowed when invoice is still pending."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        new_date = (date.today() + timedelta(days=15)).isoformat()
        await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": new_date, "reason": "x"},
        )
        resp = await client.delete(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postponements/latest",
        )
        assert resp.status_code == 204

        # Subsequent delete returns 404 (nothing to delete).
        resp = await client.delete(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postponements/latest",
        )
        assert resp.status_code == 404
