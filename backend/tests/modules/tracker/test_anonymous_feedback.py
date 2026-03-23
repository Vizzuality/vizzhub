"""Tests for anonymous feedback endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB


class TestAnonymousFeedback:
    @pytest.mark.asyncio
    async def test_create_anonymous_feedback(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 3, "year": 2026, "text": "Good vibes"},
        )
        assert resp.status_code == 201

        result = await db_session.execute(select(AnonymousFeedbackDB))
        row = result.scalar_one()
        assert row.month == 3
        assert row.year == 2026
        assert row.text == "Good vibes"

    @pytest.mark.asyncio
    async def test_anonymous_feedback_has_no_user_id_column(
        self, db_session: AsyncSession
    ):
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'anonymous_feedback'"
            )
        )
        columns = {r[0] for r in result.all()}
        assert "user_id" not in columns
        assert "created_at" not in columns
        assert "updated_at" not in columns

    @pytest.mark.asyncio
    async def test_anonymous_feedback_has_no_fk(
        self, db_session: AsyncSession
    ):
        result = await db_session.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'anonymous_feedback' "
                "AND constraint_type = 'FOREIGN KEY'"
            )
        )
        assert result.all() == []

    @pytest.mark.asyncio
    async def test_create_anonymous_feedback_validation(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 13, "year": 2026, "text": "Bad month"},
        )
        assert resp.status_code in (400, 422)

        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 3, "year": 2026, "text": ""},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_create_anonymous_feedback_duplicates_allowed(
        self, client: AsyncClient
    ):
        payload = {"month": 3, "year": 2026, "text": "Same feedback"}
        resp1 = await client.post("/api/tracker/anonymous-feedback", json=payload)
        resp2 = await client.post("/api/tracker/anonymous-feedback", json=payload)
        assert resp1.status_code == 201
        assert resp2.status_code == 201
