"""Tests for Google Workspace collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.oauth import OAuthTokenDB


class TestGoogleWorkspaceCollectorInit:
    @pytest.mark.asyncio
    async def test_init_raises_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        collector = GoogleWorkspaceCollector(db_session)
        with pytest.raises(ValueError, match="not connected"):
            await collector._init_client()

    @pytest.mark.asyncio
    async def test_init_raises_when_no_domain(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="test-token",
            site_url=None,
        )
        db_session.add(token)
        await db_session.flush()

        collector = GoogleWorkspaceCollector(db_session)
        with pytest.raises(ValueError, match="domain not configured"):
            await collector._init_client()

    @pytest.mark.asyncio
    async def test_init_creates_client(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        collector = GoogleWorkspaceCollector(db_session)
        await collector._init_client()

        assert collector._domain == "empresa.com"
        assert collector._client is not None
        await collector._client.aclose()


class TestPagination:
    @pytest.mark.asyncio
    async def test_paginate_single_page(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        collector = GoogleWorkspaceCollector(db_session)
        await collector._init_client()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "users": [{"id": "1", "primaryEmail": "a@test.com"}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await collector._paginate(
                "/users", {"customer": "my_customer"}, "users"
            )

        assert len(result) == 1
        assert result[0]["id"] == "1"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_multiple_pages(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        collector = GoogleWorkspaceCollector(db_session)
        await collector._init_client()

        page1 = MagicMock()
        page1.json.return_value = {
            "users": [{"id": "1"}],
            "nextPageToken": "token2",
        }
        page1.raise_for_status = MagicMock()

        page2 = MagicMock()
        page2.json.return_value = {
            "users": [{"id": "2"}],
        }
        page2.raise_for_status = MagicMock()

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[page1, page2],
        ):
            result = await collector._paginate(
                "/users", {"customer": "my_customer"}, "users"
            )

        assert len(result) == 2
        await collector._client.aclose()
