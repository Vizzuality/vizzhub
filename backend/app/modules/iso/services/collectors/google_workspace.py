"""Google Workspace collector for ISO access snapshots."""

import structlog
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.services.google_workspace_oauth import (
    GoogleWorkspaceOAuth,
    PROVIDER,
    SCOPES,
)

logger = structlog.get_logger()

BASE_URL = "https://admin.googleapis.com/admin/directory/v1"
COLLECTOR_VERSION = "1"


class GoogleWorkspaceCollector:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._client: httpx.AsyncClient | None = None
        self._domain: str | None = None

    async def _paginate(
        self, path: str, key: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        params = dict(params) if params else {}
        items: list[dict[str, Any]] = []
        while True:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
            items.extend(data.get(key, []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            params["pageToken"] = page_token
        return items

    async def collect_users(self) -> list[dict[str, Any]]:
        raw = await self._paginate(
            "/users", "users", {"customer": "my_customer", "maxResults": 500}
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
            "/groups", "groups", {"customer": "my_customer", "maxResults": 200}
        )
        return [
            {
                "id": g["id"],
                "email": g["email"],
                "name": g.get("name", ""),
            }
            for g in raw
        ]

    async def collect_group_members(
        self, groups: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        members: dict[str, list[dict[str, Any]]] = {}
        for group in groups:
            raw = await self._paginate(
                f"/groups/{group['email']}/members",
                "members",
                {"maxResults": 200},
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
        roles_raw = await self._paginate("/customer/my_customer/roles", "items")
        role_map = {str(r["roleId"]): r["roleName"] for r in roles_raw}

        assignments_raw = await self._paginate(
            "/customer/my_customer/roleassignments",
            "items",
            {"maxResults": 200},
        )
        return [
            {
                "user_id": a["assignedTo"],
                "role_id": str(a["roleId"]),
                "role_name": role_map.get(str(a["roleId"]), "Unknown"),
            }
            for a in assignments_raw
        ]

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
        token = await GoogleWorkspaceOAuth.get_valid_token(self.db)
        if not token:
            raise ValueError("Google Workspace not connected")

        status = await GoogleWorkspaceOAuth.get_status(self.db)
        domain = status.get("domain")
        if not domain:
            raise ValueError("Google Workspace domain not configured")

        self._domain = domain

        async with httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        ) as client:
            self._client = client

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
