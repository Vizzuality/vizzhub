"""Tests for events module API endpoints."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
        payload = _event_payload(other_costs=1500, location_city="Madrid")
        resp = await client.post("/api/events", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Climate Summit 2026"
        assert data["event_type"] == "Summit"
        assert data["theme_primary"] == "Climate"
        assert data["region_focus"] == "Europe"
        assert data["start_date"] == "2026-06-15"
        assert data["location_city"] == "Madrid"
        assert Decimal(str(data["other_costs"])) == Decimal("1500")
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
            json={"name": "Updated Summit", "other_costs": 3000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Summit"
        assert Decimal(str(data["other_costs"])) == Decimal("3000")

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

    @pytest.mark.asyncio
    @pytest.mark.parametrize("attending", ["yes", "no", "maybe", None])
    async def test_attending_round_trip(self, client: AsyncClient, attending):
        payload = _event_payload(attending=attending)
        create_resp = await client.post("/api/events", json=payload)
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["attending"] == attending

        get_resp = await client.get(f"/api/events/{created['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["attending"] == attending

    @pytest.mark.asyncio
    async def test_attending_update(self, client: AsyncClient):
        create_resp = await client.post("/api/events", json=_event_payload())
        event_id = create_resp.json()["id"]
        assert create_resp.json()["attending"] is None

        put_resp = await client.put(
            f"/api/events/{event_id}",
            json={"attending": "yes"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["attending"] == "yes"

        put_resp2 = await client.put(
            f"/api/events/{event_id}",
            json={"attending": None},
        )
        assert put_resp2.status_code == 200
        assert put_resp2.json()["attending"] is None

    @pytest.mark.asyncio
    async def test_attending_invalid_value_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/events",
            json=_event_payload(attending="going"),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_filter_attending_yes_excludes_others(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Yes Event",
                attending="yes",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="No Event",
                attending="no",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Maybe Event",
                attending="maybe",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Null Event",
            ),
        )

        resp = await client.get("/api/events?attending=yes")
        assert resp.status_code == 200
        names = sorted(i["name"] for i in resp.json()["items"])
        assert names == ["Yes Event"]

    @pytest.mark.asyncio
    async def test_filter_attending_maybe_includes_null(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Yes Event",
                attending="yes",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Maybe Event",
                attending="maybe",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Null Event",
            ),
        )

        resp = await client.get("/api/events?attending=maybe")
        assert resp.status_code == 200
        names = sorted(i["name"] for i in resp.json()["items"])
        assert names == ["Maybe Event", "Null Event"]

    @pytest.mark.asyncio
    async def test_filter_attending_invalid_rejected(self, client: AsyncClient):
        resp = await client.get("/api/events?attending=going")
        assert resp.status_code == 400


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
        assert "years_with_data" in data
        assert "Summit" in data["event_types"]
        assert "Climate" in data["themes"]
        assert "Europe" in data["regions"]
        assert "Speaker" in data["attendee_roles"]

    @pytest.mark.asyncio
    async def test_years_with_data_sorted_desc(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Old Event",
                start_date="2024-01-15",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="New Event",
                start_date="2026-06-15",
            ),
        )
        await client.post(
            "/api/events",
            json=_event_payload(
                name="Mid Event",
                start_date="2025-03-10",
            ),
        )

        resp = await client.get("/api/events/options")
        assert resp.status_code == 200
        assert resp.json()["years_with_data"] == [2026, 2025, 2024]


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
        self,
        client: AsyncClient,
        test_user: UserDB,
    ):
        create_resp = await client.post(
            "/api/events",
            json=_event_payload(other_costs=500, start_date="2025-03-10"),
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
        self,
        client: AsyncClient,
        test_user: UserDB,
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
        self,
        client: AsyncClient,
        test_user: UserDB,
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
        self,
        client: AsyncClient,
        test_user: UserDB,
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

    @pytest.mark.asyncio
    async def test_add_attendee_with_cost(
        self, client: AsyncClient, db_session: AsyncSession, test_user: UserDB
    ):
        from datetime import date

        from app.modules.events.models.event import EventDB

        event = EventDB(
            name="Cost Test",
            event_type="Conference",
            theme_primary="Climate",
            region_focus="Global",
            start_date=date(2026, 7, 1),
            other_costs=Decimal("0"),
        )
        db_session.add(event)
        await db_session.commit()

        r = await client.post(
            f"/api/events/{event.id}/attendees",
            json=[
                {
                    "user_id": str(test_user.id),
                    "role": "Speaker",
                    "cost": "150.50",
                }
            ],
        )
        assert r.status_code == 201
        assert r.json()[0]["cost"] == "150.50"

    @pytest.mark.asyncio
    async def test_patch_attendee_updates_role_and_cost(
        self, client: AsyncClient, db_session: AsyncSession, test_user: UserDB
    ):
        from datetime import date

        from app.modules.events.models.event import EventDB
        from app.modules.events.models.event_attendee import EventAttendeeDB

        event = EventDB(
            name="Patch Test",
            event_type="Conference",
            theme_primary="Climate",
            region_focus="Global",
            start_date=date(2026, 7, 2),
            other_costs=Decimal("0"),
        )
        db_session.add(event)
        await db_session.flush()
        db_session.add(
            EventAttendeeDB(
                event_id=event.id,
                user_id=test_user.id,
                role="Attendee",
                cost=None,
            )
        )
        await db_session.commit()

        r = await client.patch(
            f"/api/events/{event.id}/attendees/{test_user.id}",
            json={"role": "Panelist", "cost": "200.00"},
        )
        assert r.status_code == 200
        assert r.json()["role"] == "Panelist"
        assert r.json()["cost"] == "200.00"

    @pytest.mark.asyncio
    async def test_patch_attendee_rejects_negative_cost(
        self, client: AsyncClient, db_session: AsyncSession, test_user: UserDB
    ):
        from datetime import date

        from app.modules.events.models.event import EventDB
        from app.modules.events.models.event_attendee import EventAttendeeDB

        event = EventDB(
            name="Neg Test",
            event_type="Conference",
            theme_primary="Climate",
            region_focus="Global",
            start_date=date(2026, 7, 3),
            other_costs=Decimal("0"),
        )
        db_session.add(event)
        await db_session.flush()
        db_session.add(
            EventAttendeeDB(
                event_id=event.id,
                user_id=test_user.id,
                role="Attendee",
            )
        )
        await db_session.commit()

        r = await client.patch(
            f"/api/events/{event.id}/attendees/{test_user.id}",
            json={"cost": "-1"},
        )
        assert r.status_code == 400


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
    async def test_list_events_sort_by_total_cost_asc(self, client: AsyncClient):
        await client.post(
            "/api/events",
            json=_event_payload(name="Cheap Event", other_costs=100),
        )
        await client.post(
            "/api/events",
            json=_event_payload(name="Expensive Event", other_costs=9000),
        )

        resp = await client.get(
            "/api/events",
            params={"sort_by": "total_cost", "sort_dir": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        assert Decimal(str(items[0]["total_cost"])) < Decimal(str(items[1]["total_cost"]))
        assert items[0]["name"] == "Cheap Event"
        assert items[1]["name"] == "Expensive Event"

    @pytest.mark.asyncio
    async def test_list_events_exposes_total_cost(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from datetime import date

        from app.modules.events.models.event import EventDB
        from app.modules.events.models.event_attendee import EventAttendeeDB
        from tests.modules.events.conftest import DEBUG_USER_ID

        event = EventDB(
            name="TC",
            event_type="Conference",
            theme_primary="Climate",
            region_focus="Global",
            start_date=date(2026, 5, 1),
            other_costs=Decimal("50.00"),
        )
        db_session.add(event)
        await db_session.flush()
        db_session.add(
            EventAttendeeDB(
                event_id=event.id,
                user_id=DEBUG_USER_ID,
                role="Attendee",
                cost=Decimal("75.00"),
            )
        )
        await db_session.commit()

        r = await client.get("/api/events")
        assert r.status_code == 200
        item = next(i for i in r.json()["items"] if i["name"] == "TC")
        assert item["total_cost"] == "125.00"
        assert item["attending"] is None

    @pytest.mark.asyncio
    async def test_list_events_sort_by_total_cost(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        from datetime import date

        from app.modules.events.models.event import EventDB

        db_session.add_all(
            [
                EventDB(
                    name="A_pricey",
                    event_type="Conference",
                    theme_primary="Climate",
                    region_focus="Global",
                    start_date=date(2026, 6, 1),
                    other_costs=Decimal("1000.00"),
                ),
                EventDB(
                    name="B_cheap",
                    event_type="Conference",
                    theme_primary="Climate",
                    region_focus="Global",
                    start_date=date(2026, 6, 2),
                    other_costs=Decimal("10.00"),
                ),
            ]
        )
        await db_session.commit()

        r = await client.get("/api/events?sort_by=total_cost&sort_dir=desc")
        names = [i["name"] for i in r.json()["items"]]
        assert names.index("A_pricey") < names.index("B_cheap")
