"""Tests for Google Workspace collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from app.models.oauth import OAuthTokenDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


class TestCaptureValidation:
    @pytest.mark.asyncio
    async def test_capture_raises_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        collector = GoogleWorkspaceCollector(db_session)
        with pytest.raises(ValueError, match="not connected"):
            await collector.capture()

    @pytest.mark.asyncio
    async def test_capture_raises_when_no_domain(self, db_session) -> None:
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
            await collector.capture()


def _setup_collector_with_client(db_session):
    """Create a collector with a manually configured httpx client for unit tests."""
    from app.modules.iso.services.collectors.google_workspace import (
        GoogleWorkspaceCollector,
    )

    collector = GoogleWorkspaceCollector(db_session)
    collector._domain = "empresa.com"
    collector._client = httpx.AsyncClient(
        base_url="https://admin.googleapis.com/admin/directory/v1",
        headers={"Authorization": "Bearer ya29.test"},
        timeout=30.0,
    )
    return collector


class TestPagination:
    @pytest.mark.asyncio
    async def test_paginate_single_page(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "users": [{"id": "1", "primaryEmail": "a@test.com"}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await collector._paginate("/users", "users", {"customer": "my_customer"})

        assert len(result) == 1
        assert result[0]["id"] == "1"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_multiple_pages(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

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
            result = await collector._paginate("/users", "users", {"customer": "my_customer"})

        assert len(result) == 2
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_does_not_mutate_params(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

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

        original_params = {"customer": "my_customer"}

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[page1, page2],
        ):
            await collector._paginate("/users", "users", original_params)

        assert "pageToken" not in original_params
        await collector._client.aclose()


class TestCollectUsers:
    @pytest.mark.asyncio
    async def test_collect_users_extracts_fields(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

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
        collector = _setup_collector_with_client(db_session)

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
        collector = _setup_collector_with_client(db_session)

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
        collector = _setup_collector_with_client(db_session)

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
        collector = _setup_collector_with_client(db_session)

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
        collector = _setup_collector_with_client(db_session)

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


class TestBuildSummary:
    def test_build_summary(self) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        collector = GoogleWorkspaceCollector.__new__(GoogleWorkspaceCollector)
        collector._domain = "empresa.com"

        data = {
            "users": [
                {
                    "id": "u1",
                    "email": "a@empresa.com",
                    "name": "A",
                    "suspended": False,
                    "org_unit_path": "/",
                },
                {
                    "id": "u2",
                    "email": "b@empresa.com",
                    "name": "B",
                    "suspended": True,
                    "org_unit_path": "/",
                },
                {
                    "id": "u3",
                    "email": "c@empresa.com",
                    "name": "C",
                    "suspended": False,
                    "org_unit_path": "/",
                },
            ],
            "groups": [
                {"id": "g1", "email": "team@empresa.com", "name": "Team"},
            ],
            "group_members": {
                "team@empresa.com": [
                    {"email": "a@empresa.com", "role": "OWNER", "type": "USER"},
                    {"email": "ext@vendor.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [
                {
                    "user_id": "u1",
                    "role_id": "1",
                    "role_name": "Super Admin",
                    "user_email": "a@empresa.com",
                },
            ],
        }

        summary = collector._build_summary(data)

        assert summary["total_users"] == 3
        assert summary["active_users"] == 2
        assert summary["suspended_users"] == 1
        assert summary["total_admins"] == 1
        assert summary["external_members"] == 1
        assert summary["total_groups"] == 1


class TestBuildSourceMetadata:
    def test_build_source_metadata(self) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        collector = GoogleWorkspaceCollector.__new__(GoogleWorkspaceCollector)
        collector._domain = "empresa.com"

        meta = collector._build_source_metadata("manual")

        assert meta["domain"] == "empresa.com"
        assert meta["collector"] == "google_workspace"
        assert meta["collector_version"] == "1"
        assert meta["run_mode"] == "manual"
        assert (
            "https://www.googleapis.com/auth/admin.directory.user.readonly"
            in meta["scopes"]
        )


class TestCapture:
    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(self, db_session) -> None:
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

        users_resp = MagicMock()
        users_resp.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "a@empresa.com",
                    "name": {"fullName": "A"},
                    "suspended": False,
                    "orgUnitPath": "/",
                },
            ],
        }
        users_resp.raise_for_status = MagicMock()

        groups_resp = MagicMock()
        groups_resp.json.return_value = {
            "groups": [
                {"id": "g1", "email": "team@empresa.com", "name": "Team"},
            ],
        }
        groups_resp.raise_for_status = MagicMock()

        members_resp = MagicMock()
        members_resp.json.return_value = {
            "members": [
                {"email": "a@empresa.com", "role": "MEMBER", "type": "USER"},
            ],
        }
        members_resp.raise_for_status = MagicMock()

        roles_resp = MagicMock()
        roles_resp.json.return_value = {
            "items": [{"roleId": "1001", "roleName": "Super Admin"}],
        }
        roles_resp.raise_for_status = MagicMock()

        assignments_resp = MagicMock()
        assignments_resp.json.return_value = {
            "items": [{"assignedTo": "u1", "roleId": "1001"}],
        }
        assignments_resp.raise_for_status = MagicMock()

        collector = GoogleWorkspaceCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[
                users_resp,
                groups_resp,
                members_resp,
                roles_resp,
                assignments_resp,
            ],
        ):
            snapshot = await collector.capture(run_mode="manual")

        assert isinstance(snapshot, AccessSnapshotDB)
        assert snapshot.provider == "google_workspace"
        assert snapshot.data_version == "1"
        assert len(snapshot.data["users"]) == 1
        assert len(snapshot.data["groups"]) == 1
        assert snapshot.summary["total_users"] == 1
        assert snapshot.summary["total_admins"] == 1
        assert snapshot.source_metadata["domain"] == "empresa.com"
        assert snapshot.source_metadata["run_mode"] == "manual"

    @pytest.mark.asyncio
    async def test_capture_maps_user_email_to_role_assignments(
        self, db_session
    ) -> None:
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

        users_resp = MagicMock()
        users_resp.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "admin@empresa.com",
                    "name": {"fullName": "Admin"},
                    "suspended": False,
                    "orgUnitPath": "/",
                },
            ],
        }
        users_resp.raise_for_status = MagicMock()

        groups_resp = MagicMock()
        groups_resp.json.return_value = {"groups": []}
        groups_resp.raise_for_status = MagicMock()

        roles_resp = MagicMock()
        roles_resp.json.return_value = {
            "items": [{"roleId": "1001", "roleName": "Super Admin"}],
        }
        roles_resp.raise_for_status = MagicMock()

        assignments_resp = MagicMock()
        assignments_resp.json.return_value = {
            "items": [{"assignedTo": "u1", "roleId": "1001"}],
        }
        assignments_resp.raise_for_status = MagicMock()

        collector = GoogleWorkspaceCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[users_resp, groups_resp, roles_resp, assignments_resp],
        ):
            snapshot = await collector.capture(run_mode="manual")

        ra = snapshot.data["role_assignments"][0]
        assert ra["user_email"] == "admin@empresa.com"
