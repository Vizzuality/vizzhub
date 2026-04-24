"""Tests for events module API endpoints."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.models.user import UserDB


def _event_payload(**overrides) -> dict:
    """Build a valid event creation payload with sensible defaults."""
    base = {
        "name": "Climate Summit 2026",
        "event_type": "Summit",
        "theme_primary": "Climate",
        "region_focus": "Europe",
        "start_date": "2026-06-15",
    }
    base.update(overrides)
    return base


class TestEventsCRUD:
    @pytest.mark.asyncio
    async def test_list_events_empty(self, client: AsyncClient):
        resp = await client.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_create_event(self, client: AsyncClient):
        payload = _event_payload(cost=1500, location_city="Madrid")
        resp = await client.post("/api/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Climate Summit 2026"
        assert data["event_type"] == "Summit"
        assert data["theme_primary"] == "Climate"
        assert data["region_focus"] == "Europe"
        assert data["start_date"] == "2026-06-15"
        assert data["location_city"] == "Madrid"
        assert Decimal(str(data["cost"])) == Decimal("1500")
        assert data["attendee_count"] == 0
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_event_detail(self, client: AsyncClient):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        resp = await client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == event_id
        assert data["name"] == "Climate Summit 2026"
        assert data["attendees"] == []

    @pytest.mark.asyncio
    async def test_update_event(self, client: AsyncClient):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/events/{event_id}",
            json={"name": "Updated Summit", "cost": 3000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Summit"
        assert Decimal(str(data["cost"])) == Decimal("3000")

    @pytest.mark.asyncio
    async def test_delete_event(self, client: AsyncClient):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/events/{event_id}")
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/events/{event_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, client: AsyncClient):
        fake_id = str(uuid4())
        resp = await client.get(f"/api/events/{fake_id}")
        assert resp.status_code == 404


class TestEventOptions:
    @pytest.mark.asyncio
    async def test_get_options(self, client: AsyncClient):
        resp = await client.get("/api/events/options")
        assert resp.status_code == 200
        data = resp.json()
        assert "event_types" in data
        assert "themes" in data
        assert "regions" in data
        assert "attendee_roles" in data
        assert "Summit" in data["event_types"]
        assert "Climate" in data["themes"]
        assert "Europe" in data["regions"]
        assert "Speaker" in data["attendee_roles"]


class TestEventStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty(self, client: AsyncClient):
        resp = await client.get("/api/events/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 0
        assert Decimal(str(data["total_cost"])) == Decimal("0")
        assert data["total_attendees"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(
        self, client: AsyncClient, test_user: UserDB,
    ):
        create_resp = await client.post(
            "/api/events",
            json=_event_payload(cost=500, start_date="2025-03-10"),
        )
        event_id = create_resp.json()["id"]
        await client.post(
            f"/api/events/{event_id}/attendees",
            json=[{"user_id": str(test_user.id), "role": "Speaker"}],
        )

        resp = await client.get("/api/events/stats", params={"year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] == 1
        assert data["total_attendees"] == 1
        assert Decimal(str(data["total_cost"])) == Decimal("500")
        assert any(g["label"] == "Climate" for g in data["by_theme"])
        assert any(g["label"] == "Speaker" for g in data["by_role"])


class TestEventAttendees:
    @pytest.mark.asyncio
    async def test_add_attendee(
        self, client: AsyncClient, test_user: UserDB,
    ):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/events/{event_id}/attendees",
            json=[{"user_id": str(test_user.id), "role": "Speaker"}],
        )
        assert resp.status_code == 201
        attendees = resp.json()
        assert len(attendees) == 1
        assert attendees[0]["user_id"] == str(test_user.id)
        assert attendees[0]["role"] == "Speaker"

        detail_resp = await client.get(f"/api/events/{event_id}")
        detail = detail_resp.json()
        assert len(detail["attendees"]) == 1
        assert detail["attendee_count"] == 1

    @pytest.mark.asyncio
    async def test_remove_attendee(
        self, client: AsyncClient, test_user: UserDB,
    ):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        await client.post(
            f"/api/events/{event_id}/attendees",
            json=[{"user_id": str(test_user.id), "role": "Attendee"}],
        )

        resp = await client.delete(
            f"/api/events/{event_id}/attendees/{test_user.id}",
        )
        assert resp.status_code == 204

        detail_resp = await client.get(f"/api/events/{event_id}")
        assert detail_resp.json()["attendees"] == []

    @pytest.mark.asyncio
    async def test_duplicate_attendee_returns_409(
        self, client: AsyncClient, test_user: UserDB,
    ):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]

        await client.post(
            f"/api/events/{event_id}/attendees",
            json=[{"user_id": str(test_user.id), "role": "Speaker"}],
        )

        resp = await client.post(
            f"/api/events/{event_id}/attendees",
            json=[{"user_id": str(test_user.id), "role": "Panelist"}],
        )
        assert resp.status_code == 409


class TestEventFiltering:
    @pytest.mark.asyncio
    async def test_list_events_with_search(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(name="Ocean Conference"),
        )
        await client.post(
            "/api/events",
            json=_event_payload(name="Forest Workshop"),
        )

        resp = await client.get("/api/events", params={"search": "Ocean"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Ocean Conference"

    @pytest.mark.asyncio
    async def test_list_events_sort_by_cost(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(name="Cheap Event", cost=100),
        )
        await client.post(
            "/api/events",
            json=_event_payload(name="Expensive Event", cost=9000),
        )

        resp = await client.get(
            "/api/events",
            params={"sort_by": "cost", "sort_dir": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        assert Decimal(str(items[0]["cost"])) < Decimal(str(items[1]["cost"]))
        assert items[0]["name"] == "Cheap Event"
        assert items[1]["name"] == "Expensive Event"
