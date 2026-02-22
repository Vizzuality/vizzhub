# Phase 3: Google Workspace Collector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Google Workspace collector that fetches users, groups, members, and role assignments via Google Admin Directory REST API, then builds a structured snapshot.

**Architecture:** Single `GoogleWorkspaceCollector` class using httpx directly against the Google Admin Directory REST API (not google-api-python-client). The collector gets a valid OAuth token from `GoogleWorkspaceOAuth.get_valid_token()`, uses a generic `_paginate` helper for all endpoints, and produces a dict matching the `AccessSnapshotDB.data` schema from the design doc.

**Tech Stack:** httpx (async HTTP), SQLAlchemy 2.0 async, pytest + unittest.mock

---

### Task 1: Collector skeleton with client init and pagination helper

**Files:**
- Create: `backend/app/modules/iso/services/collectors/google_workspace.py`
- Test: `backend/tests/test_iso_collector.py`

**Step 1: Write the failing tests**

```python
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
            result = await collector._paginate("/users", {"customer": "my_customer"}, "users")

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
            collector._client, "get", new_callable=AsyncMock, side_effect=[page1, page2]
        ):
            result = await collector._paginate("/users", {"customer": "my_customer"}, "users")

        assert len(result) == 2
        await collector._client.aclose()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_collector.py -v --no-header -q`
Expected: FAIL with ImportError (module doesn't exist yet)

**Step 3: Write minimal implementation**

```python
"""Google Workspace collector for ISO access snapshots."""

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.services.google_workspace_oauth import (
    GoogleWorkspaceOAuth,
    PROVIDER,
    SCOPES,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://admin.googleapis.com/admin/directory/v1"
COLLECTOR_VERSION = "1"


class GoogleWorkspaceCollector:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._client: httpx.AsyncClient | None = None
        self._domain: str | None = None

    async def _init_client(self) -> None:
        token = await GoogleWorkspaceOAuth.get_valid_token(self.db)
        if not token:
            raise ValueError("Google Workspace not connected")

        status = await GoogleWorkspaceOAuth.get_status(self.db)
        domain = status.get("domain")
        if not domain:
            raise ValueError("Google Workspace domain not configured")

        self._domain = domain
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def _paginate(
        self, path: str, params: dict[str, Any], result_key: str
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
            items.extend(data.get(result_key, []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params["pageToken"] = page_token
        return items
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_collector.py -v --no-header -q`
Expected: 5 passed

**Step 5: Commit**

```bash
git add tests/test_iso_collector.py app/modules/iso/services/collectors/google_workspace.py
git commit -m "feat(iso): add collector skeleton with pagination helper"
```

---

### Task 2: Implement collect_users() and collect_groups()

**Files:**
- Modify: `backend/app/modules/iso/services/collectors/google_workspace.py`
- Modify: `backend/tests/test_iso_collector.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_collector.py`:

```python
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
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
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
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
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
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            groups = await collector.collect_groups()

        assert len(groups) == 1
        assert groups[0] == {
            "id": "group-1",
            "email": "devops@empresa.com",
            "name": "DevOps Team",
        }
        await collector._client.aclose()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_collector.py::TestCollectUsers -v --no-header -q`
Expected: FAIL with AttributeError (methods don't exist yet)

**Step 3: Add to `google_workspace.py` class**

```python
    async def collect_users(self) -> list[dict[str, Any]]:
        raw = await self._paginate(
            "/users", {"customer": "my_customer", "maxResults": 500}, "users"
        )
        return [
            {
                "id": u["id"],
                "email": u["primaryEmail"],
                "name": u.get("name", {}).get("fullName", ""),
                "suspended": u.get("suspended", False),
                "org_unit_path": u.get("orgUnitPath", "/"),
            }
            for u in raw
        ]

    async def collect_groups(self) -> list[dict[str, Any]]:
        raw = await self._paginate(
            "/groups", {"customer": "my_customer", "maxResults": 200}, "groups"
        )
        return [
            {
                "id": g["id"],
                "email": g["email"],
                "name": g.get("name", ""),
            }
            for g in raw
        ]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_collector.py -v --no-header -q`
Expected: 8 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/collectors/google_workspace.py tests/test_iso_collector.py
git commit -m "feat(iso): add collect_users and collect_groups"
```

---

### Task 3: Implement collect_group_members() and collect_role_assignments()

**Files:**
- Modify: `backend/app/modules/iso/services/collectors/google_workspace.py`
- Modify: `backend/tests/test_iso_collector.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_collector.py`:

```python
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
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
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
            collector._client, "get", new_callable=AsyncMock, return_value=mock_response
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_collector.py::TestCollectGroupMembers tests/test_iso_collector.py::TestCollectRoleAssignments -v --no-header -q`
Expected: FAIL with AttributeError

**Step 3: Add to `google_workspace.py` class**

```python
    async def collect_group_members(
        self, groups: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        members: dict[str, list[dict[str, Any]]] = {}
        for group in groups:
            raw = await self._paginate(
                f"/groups/{group['email']}/members",
                {"maxResults": 200},
                "members",
            )
            members[group["email"]] = [
                {
                    "email": m.get("email", ""),
                    "role": m.get("role", "MEMBER"),
                    "type": m.get("type", "USER"),
                }
                for m in raw
            ]
        return members

    async def collect_role_assignments(self) -> list[dict[str, Any]]:
        roles_raw = await self._paginate(
            "/customer/my_customer/roles", {}, "items"
        )
        role_map = {str(r["roleId"]): r["roleName"] for r in roles_raw}

        assignments_raw = await self._paginate(
            "/customer/my_customer/roleassignments",
            {"maxResults": 200},
            "items",
        )
        return [
            {
                "user_id": a["assignedTo"],
                "role_id": str(a["roleId"]),
                "role_name": role_map.get(str(a["roleId"]), "Unknown"),
            }
            for a in assignments_raw
        ]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_collector.py -v --no-header -q`
Expected: 12 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/collectors/google_workspace.py tests/test_iso_collector.py
git commit -m "feat(iso): add collect_group_members and collect_role_assignments"
```

---

### Task 4: Implement capture() orchestrator, build_summary(), build_source_metadata()

**Files:**
- Modify: `backend/app/modules/iso/services/collectors/google_workspace.py`
- Modify: `backend/tests/test_iso_collector.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_collector.py`:

```python
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


class TestBuildSummary:
    def test_build_summary(self) -> None:
        from app.modules.iso.services.collectors.google_workspace import (
            GoogleWorkspaceCollector,
        )

        collector = GoogleWorkspaceCollector.__new__(GoogleWorkspaceCollector)
        collector._domain = "empresa.com"

        data = {
            "users": [
                {"id": "u1", "email": "a@empresa.com", "name": "A", "suspended": False, "org_unit_path": "/"},
                {"id": "u2", "email": "b@empresa.com", "name": "B", "suspended": True, "org_unit_path": "/"},
                {"id": "u3", "email": "c@empresa.com", "name": "C", "suspended": False, "org_unit_path": "/"},
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
                {"user_id": "u1", "role_id": "1", "role_name": "Super Admin", "user_email": "a@empresa.com"},
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
        assert "admin.directory.user.readonly" in meta["scopes"]


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
                {"id": "u1", "primaryEmail": "a@empresa.com", "name": {"fullName": "A"}, "suspended": False, "orgUnitPath": "/"},
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
            side_effect=[users_resp, groups_resp, members_resp, roles_resp, assignments_resp],
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
    async def test_capture_maps_user_email_to_role_assignments(self, db_session) -> None:
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
                {"id": "u1", "primaryEmail": "admin@empresa.com", "name": {"fullName": "Admin"}, "suspended": False, "orgUnitPath": "/"},
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_collector.py::TestCapture tests/test_iso_collector.py::TestBuildSummary tests/test_iso_collector.py::TestBuildSourceMetadata -v --no-header -q`
Expected: FAIL with AttributeError

**Step 3: Add to `google_workspace.py`**

Add these imports at top:

```python
from datetime import datetime, timezone
from uuid import UUID

from app.modules.iso.models.access_snapshot import AccessSnapshotDB
```

Add these methods to the class:

```python
    def _build_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        users = data["users"]
        role_assignments = data["role_assignments"]
        admin_user_ids = {a["user_id"] for a in role_assignments}

        external_count = 0
        for members_list in data["group_members"].values():
            for m in members_list:
                email = m.get("email", "")
                if email and not email.endswith(f"@{self._domain}"):
                    external_count += 1

        return {
            "total_users": len(users),
            "active_users": sum(1 for u in users if not u["suspended"]),
            "suspended_users": sum(1 for u in users if u["suspended"]),
            "total_admins": len(admin_user_ids),
            "external_members": external_count,
            "total_groups": len(data["groups"]),
        }

    def _build_source_metadata(self, run_mode: str) -> dict[str, Any]:
        return {
            "domain": self._domain,
            "collector": "google_workspace",
            "collector_version": COLLECTOR_VERSION,
            "scopes": SCOPES.split(" "),
            "run_mode": run_mode,
        }

    async def capture(
        self,
        captured_by: UUID | None = None,
        run_mode: str = "manual",
    ) -> AccessSnapshotDB:
        await self._init_client()
        try:
            users = await self.collect_users()
            groups = await self.collect_groups()
            group_members = await self.collect_group_members(groups)
            role_assignments = await self.collect_role_assignments()

            user_id_to_email = {u["id"]: u["email"] for u in users}
            for ra in role_assignments:
                ra["user_email"] = user_id_to_email.get(ra["user_id"], "")

            data = {
                "users": users,
                "groups": groups,
                "group_members": group_members,
                "role_assignments": role_assignments,
            }

            snapshot = AccessSnapshotDB(
                provider=PROVIDER,
                captured_at=datetime.now(timezone.utc),
                captured_by=captured_by,
                data_version="1",
                source_metadata=self._build_source_metadata(run_mode),
                data=data,
                summary=self._build_summary(data),
            )
            self.db.add(snapshot)
            await self.db.flush()
            return snapshot
        finally:
            await self._client.aclose()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_collector.py -v --no-header -q`
Expected: 16 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/collectors/google_workspace.py tests/test_iso_collector.py
git commit -m "feat(iso): add capture orchestrator with summary and metadata"
```

---

### Task 5: Export collector from __init__.py and run full regression

**Files:**
- Modify: `backend/app/modules/iso/services/collectors/__init__.py`

**Step 1: Update the collectors __init__.py**

```python
from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)

__all__ = ["GoogleWorkspaceCollector"]
```

**Step 2: Run full regression test suite**

Run: `pytest tests/ -x -q`
Expected: 880+ passed (864 existing + 16 new)

**Step 3: Run lint**

Run: `ruff check app/modules/iso/ && black --check app/modules/iso/`
Expected: All checks passed. If Black fails, run `black app/modules/iso/` and commit the fix.

**Step 4: Commit**

```bash
git add app/modules/iso/services/collectors/__init__.py
git commit -m "feat(iso): export GoogleWorkspaceCollector from collectors package"
```
