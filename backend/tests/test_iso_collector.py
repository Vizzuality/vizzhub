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


class TestCollectUsers:
    @pytest.mark.asyncio
    async def test_collect_users_extracts_fields(self, db_session) -> None:
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
            "users": [
                {
                    "id": "user-1",
                    "primaryEmail": "maria@empresa.com",
                    "name": {"fullName": "Maria Lopez"},
                    "suspended": False,
                    "orgUnitPath": "/Engineering",
                },
                {
                    "id": "user-2",
                    "primaryEmail": "carlos@empresa.com",
                    "name": {"fullName": "Carlos Ruiz"},
                    "suspended": True,
                    "orgUnitPath": "/",
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            users = await collector.collect_users()

        assert len(users) == 2
        assert users[0] == {
            "id": "user-1",
            "email": "maria@empresa.com",
            "name": "Maria Lopez",
            "suspended": False,
            "org_unit_path": "/Engineering",
        }
        assert users[1]["suspended"] is True
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_collect_users_handles_missing_fields(self, db_session) -> None:
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
            "users": [{"id": "u1", "primaryEmail": "x@t.com"}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            users = await collector.collect_users()

        assert users[0]["name"] == ""
        assert users[0]["suspended"] is False
        assert users[0]["org_unit_path"] == "/"
        await collector._client.aclose()


class TestCollectGroups:
    @pytest.mark.asyncio
    async def test_collect_groups_extracts_fields(self, db_session) -> None:
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
            "groups": [
                {
                    "id": "group-1",
                    "email": "devops@empresa.com",
                    "name": "DevOps Team",
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            groups = await collector.collect_groups()

        assert len(groups) == 1
        assert groups[0] == {
            "id": "group-1",
            "email": "devops@empresa.com",
            "name": "DevOps Team",
        }
        await collector._client.aclose()


class TestCollectGroupMembers:
    @pytest.mark.asyncio
    async def test_collect_group_members(self, db_session) -> None:
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
            "members": [
                {"email": "maria@empresa.com", "role": "OWNER", "type": "USER"},
                {"email": "external@vendor.com", "role": "MEMBER", "type": "USER"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        groups = [{"id": "g1", "email": "devops@empresa.com", "name": "DevOps"}]

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            members = await collector.collect_group_members(groups)

        assert "devops@empresa.com" in members
        assert len(members["devops@empresa.com"]) == 2
        assert members["devops@empresa.com"][0]["email"] == "maria@empresa.com"
        assert members["devops@empresa.com"][0]["role"] == "OWNER"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_collect_group_members_empty_group(self, db_session) -> None:
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
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        groups = [{"id": "g1", "email": "empty@empresa.com", "name": "Empty"}]

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            members = await collector.collect_group_members(groups)

        assert members["empty@empresa.com"] == []
        await collector._client.aclose()


class TestCollectRoleAssignments:
    @pytest.mark.asyncio
    async def test_collect_role_assignments(self, db_session) -> None:
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

        roles_response = MagicMock()
        roles_response.json.return_value = {
            "items": [
                {"roleId": "1001", "roleName": "Super Admin"},
                {"roleId": "1002", "roleName": "Groups Admin"},
            ],
        }
        roles_response.raise_for_status = MagicMock()

        assignments_response = MagicMock()
        assignments_response.json.return_value = {
            "items": [
                {"assignedTo": "user-1", "roleId": "1001"},
                {"assignedTo": "user-2", "roleId": "1002"},
            ],
        }
        assignments_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[roles_response, assignments_response],
        ):
            assignments = await collector.collect_role_assignments()

        assert len(assignments) == 2
        assert assignments[0]["user_id"] == "user-1"
        assert assignments[0]["role_name"] == "Super Admin"
        assert assignments[1]["role_name"] == "Groups Admin"
        await collector._client.aclose()
