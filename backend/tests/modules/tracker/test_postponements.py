"""Tests for invoice postponement math and window boundaries.

Postpone rules (see app/modules/tracker/api/postponements.py):
- Only `pending_to_issue` invoices can be postponed.
- `base_date` = latest existing postponement date, else invoice.due_date.
- `window_base` = max(base_date, today)
- new date must be > base_date AND <= window_base + MAX_POSTPONE_DAYS (30).
- Paid / voided invoices cannot have their postponements deleted.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB

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
        self,
        client: AsyncClient,
        db_session: AsyncSession,
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
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
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
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
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
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
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
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
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

    async def test_postpone_to_past_date_rejected(
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
    ) -> None:
        """Backdated postponement (postponed_to in the past) must be rejected
        even when base_date is older than today. Audit finding #28."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        past = (date.today() - timedelta(days=5)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": past, "reason": "should not work"},
        )
        assert resp.status_code == 400
        assert "after" in resp.json()["detail"].lower()

    async def test_postpone_exactly_at_window_boundary(
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
    ) -> None:
        """window_base + 30 succeeds; +31 fails. Boundary is inclusive on the high side."""
        pid = setup_pending_invoice["project_id"]
        inv_id = setup_pending_invoice["invoice_id"]

        # window_base = today (due_date is today-10), so today+30 is the inclusive max.
        at_boundary = (date.today() + timedelta(days=30)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": at_boundary, "reason": "max allowed"},
        )
        assert resp.status_code == 201, resp.text

        # Clear the postponement so we can retry with the over-boundary date.
        await client.delete(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postponements/latest",
        )

        past_boundary = (date.today() + timedelta(days=31)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": past_boundary, "reason": "over"},
        )
        assert resp.status_code == 400
        assert "30 days" in resp.json()["detail"]

    async def test_postpone_when_base_date_is_today(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """When base_date == today, today+30 is allowed; today+31 is not."""
        user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
        db_session.add(user)
        await db_session.flush()
        project = ProjectDB(name="Today Proj", status="live")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        pid = str(project.id)

        today_iso = date.today().isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices",
            json={
                "amount": 1000,
                "code": "INV-TODAY",
                "due_date": today_iso,
                "milestone": "M1",
            },
        )
        assert resp.status_code == 201, resp.text
        inv_id = resp.json()["id"]

        at_boundary = (date.today() + timedelta(days=30)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": at_boundary, "reason": "max"},
        )
        assert resp.status_code == 201, resp.text

        await client.delete(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postponements/latest",
        )

        past_boundary = (date.today() + timedelta(days=31)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": past_boundary, "reason": "over"},
        )
        assert resp.status_code == 400
        assert "30 days" in resp.json()["detail"]

    async def test_delete_latest_postponement(
        self,
        client: AsyncClient,
        setup_pending_invoice: dict,
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


# --- Effective-status regression tests (audit finding #27) -------------------


async def _seed_user_project_invoice(
    db_session: AsyncSession, due_offset_days: int = -10
) -> tuple[str, str, InvoiceDB]:
    """Helper: seed user + project + pending_to_issue invoice via direct DB
    inserts so individual postponements can be controlled per test."""
    user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(name="Postpone Project", status="live")
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)

    invoice = InvoiceDB(
        project_id=project.id,
        code="INV-RGS",
        amount=1000,
        due_date=date.today() + timedelta(days=due_offset_days),
        milestone="M1",
        status="pending_to_issue",
    )
    db_session.add(invoice)
    await db_session.flush()
    await db_session.refresh(invoice)
    await db_session.commit()
    return str(project.id), str(invoice.id), invoice


@pytest.mark.asyncio
class TestEffectiveStatusMostRecent:
    async def test_effective_status_uses_most_recent_postponement_not_max_date(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """When two postponements exist, the most-recently-created one wins —
        not the one with the maximum ``postponed_to`` date. Audit #27."""
        pid, inv_id, invoice = await _seed_user_project_invoice(db_session)

        far_future = date.today() + timedelta(days=30)
        correction = date.today() + timedelta(days=5)

        # Insert the far-future postponement first, then the corrective one.
        # created_at is set via server_default=func.now(); we set explicit
        # values to guarantee ordering regardless of DB clock resolution.
        now = datetime.now(UTC)
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=far_future,
                reason="initial postpone",
                created_at=now - timedelta(minutes=10),
            )
        )
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=correction,
                reason="corrected closer in",
                created_at=now,
            )
        )
        await db_session.commit()

        # SQL CASE path (list endpoint).
        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        inv = items[0]
        assert inv["status"] == "postponed"
        assert inv["postponed_to"] == correction.isoformat()
        assert inv["postpone_count"] == 2

    async def test_effective_status_boundary_today(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """``postponed_to == today`` → ``pending_to_issue`` (postponed branch
        uses strict ``> today``). Audit #27 boundary."""
        pid, _inv_id, invoice = await _seed_user_project_invoice(db_session)
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=date.today(),
                reason="expires today",
            )
        )
        await db_session.commit()

        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["status"] == "pending_to_issue"
        # postponed_to is only surfaced when status is "postponed".
        assert items[0]["postponed_to"] is None
        assert items[0]["postpone_count"] == 1

    async def test_invoice_status_info_python_matches_sql(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The Python ``_invoice_status_info`` (used by create/update/transition
        responses) must agree with the SQL CASE (used by the list endpoint) on
        the same fixture. Guards the duplication called out in audit #27."""
        pid, inv_id, invoice = await _seed_user_project_invoice(db_session)

        now = datetime.now(UTC)
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=date.today() + timedelta(days=20),
                reason="first",
                created_at=now - timedelta(minutes=5),
            )
        )
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=date.today() + timedelta(days=8),
                reason="correction",
                created_at=now,
            )
        )
        await db_session.commit()

        list_resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert list_resp.status_code == 200, list_resp.text
        sql_view = list_resp.json()[0]

        # Trigger the Python path via update (no-op patch).
        update_resp = await client.put(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}",
            json={"observations": "ping"},
        )
        assert update_resp.status_code == 200, update_resp.text
        py_view = update_resp.json()

        assert sql_view["status"] == py_view["status"] == "postponed"
        assert sql_view["postponed_to"] == py_view["postponed_to"]
        assert sql_view["postpone_count"] == py_view["postpone_count"] == 2

    async def test_postponement_correction_updates_effective_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """End-to-end: an earlier far-future postponement plus a later corrective
        one must surface the corrective date through the GET list endpoint.
        Closes audit #27 against the read path."""
        pid, inv_id, invoice = await _seed_user_project_invoice(db_session)

        # First postponement via the API (the legitimate happy path).
        far = (date.today() + timedelta(days=30)).isoformat()
        resp = await client.post(
            f"/api/tracker/projects/{pid}/invoices/{inv_id}/postpone",
            json={"postponed_to": far, "reason": "client delay"},
        )
        assert resp.status_code == 201, resp.text

        # Corrective postponement (closer in). The API blocks a second
        # postponement while one is active, so insert directly — the bug under
        # test is on the read path, not the write path.
        near = date.today() + timedelta(days=10)
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=near,
                reason="corrected",
                created_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
        await db_session.commit()

        resp = await client.get(f"/api/tracker/projects/{pid}/invoices")
        assert resp.status_code == 200, resp.text
        inv = resp.json()[0]
        assert inv["status"] == "postponed"
        assert inv["postponed_to"] == near.isoformat()
        assert inv["postpone_count"] == 2
