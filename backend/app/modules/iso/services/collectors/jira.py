"""Jira collector for ISO access snapshots."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.oauth_service import OAuthService
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

logger = structlog.get_logger()

COLLECTOR_VERSION = "2"
PROVIDER = "jira"
REQUIRED_SCOPES = ["read:jira-user"]
ADMIN_GROUPS = {"jira-administrators", "site-admins"}
USERS_PAGE_SIZE = 50
GROUPS_PAGE_SIZE = 50


class JiraCollector:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._client: httpx.AsyncClient | None = None
        self._site_url: str | None = None
        self._cloud_id: str | None = None
        self._token: str | None = None

    async def _paginate_array(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate endpoints that return flat arrays (users/search)."""
        params = dict(params) if params else {}
        params.setdefault("maxResults", USERS_PAGE_SIZE)
        items: list[dict[str, Any]] = []
        start_at = 0

        while True:
            params["startAt"] = start_at
            response = await self._client.get(path, params=params)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list) or len(data) == 0:
                break

            items.extend(data)
            start_at += len(data)

        return items

    async def _paginate_values(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate endpoints that return {values, isLast} objects."""
        params = dict(params) if params else {}
        params.setdefault("maxResults", GROUPS_PAGE_SIZE)
        items: list[dict[str, Any]] = []
        start_at = 0

        while True:
            params["startAt"] = start_at
            response = await self._client.get(path, params=params)
            response.raise_for_status()

            data = response.json()
            values = data.get("values", [])
            items.extend(values)

            if data.get("isLast", True):
                break

            start_at += len(values)

        return items

    def _get_org_domain(self) -> str | None:
        """Derive org email domain from site_url (e.g. 'https://vizzuality.atlassian.net' → 'vizzuality.com')."""
        if not self._site_url:
            return None
        from urllib.parse import urlparse

        host = urlparse(self._site_url).hostname or ""
        subdomain = host.split(".")[0] if "." in host else ""
        return f"{subdomain}.com" if subdomain else None

    async def collect_users(self) -> list[dict[str, Any]]:
        raw = await self._paginate_array("/rest/api/3/users/search")
        org_domain = self._get_org_domain()

        users = []
        for u in raw:
            if not u.get("active", True):
                continue
            if u.get("accountType") in ("app", "customer"):
                continue
            email = u.get("emailAddress")
            is_external = True
            if org_domain and email and "@" in email:
                is_external = email.rsplit("@", 1)[-1].lower() != org_domain
            users.append(
                {
                    "account_id": u["accountId"],
                    "email": email,
                    "display_name": u.get("displayName", ""),
                    "account_type": u.get("accountType", "atlassian"),
                    "is_external": is_external,
                }
            )
        return users

    async def collect_groups(self) -> list[dict[str, Any]]:
        raw = await self._paginate_values("/rest/api/3/group/bulk")
        return [
            {
                "group_id": g["groupId"],
                "name": g["name"],
            }
            for g in raw
        ]

    async def collect_group_members(
        self,
        users: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Build group→members map by querying each user's groups via /user/groups."""
        group_names = {g["name"] for g in groups}
        members: dict[str, list[dict[str, Any]]] = {name: [] for name in group_names}

        for user in users:
            response = await self._client.get(
                "/rest/api/3/user/groups",
                params={"accountId": user["account_id"]},
            )
            if response.status_code != 200:
                logger.warning(
                    "jira_user_groups_fetch_failed",
                    status_code=response.status_code,
                    account_id=user["account_id"],
                )
                continue

            user_groups = response.json()
            member_entry = {
                "account_id": user["account_id"],
                "display_name": user.get("display_name", ""),
            }
            for g in user_groups:
                name = g.get("name", "")
                if name in group_names:
                    members[name].append(member_entry)

        return members

    def _build_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        users = data["users"]
        group_members = data.get("group_members", {})

        admin_ids: set[str] = set()
        for group_name, members in group_members.items():
            if group_name in ADMIN_GROUPS:
                for m in members:
                    admin_ids.add(m["account_id"])

        return {
            "total_users": len(users),
            "total_admins": len(admin_ids),
            "total_groups": len(data["groups"]),
            "external_users": sum(1 for u in users if u.get("is_external")),
        }

    def _build_source_metadata(self, run_mode: str) -> dict[str, Any]:
        return {
            "site_url": self._site_url,
            "collector": "jira",
            "collector_version": COLLECTOR_VERSION,
            "scopes": REQUIRED_SCOPES,
            "run_mode": run_mode,
        }

    async def capture(
        self,
        captured_by: UUID | None = None,
        run_mode: str = "manual",
    ) -> AccessSnapshotDB:
        token = await OAuthService.get_valid_jira_token(self.db)
        if not token:
            raise ValueError("Jira token not configured")

        site_info = await OAuthService.get_jira_site_info(self.db)
        if not site_info or not site_info.get("cloud_id"):
            raise ValueError("Jira site info not configured")

        self._cloud_id = site_info["cloud_id"]
        self._site_url = site_info.get("site_url")
        self._token = token

        base_url = f"https://api.atlassian.com/ex/jira/{self._cloud_id}"

        async with httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        ) as client:
            self._client = client

            users = await self.collect_users()
            groups = await self.collect_groups()
            group_members = await self.collect_group_members(users, groups)

        data = {
            "users": users,
            "groups": groups,
            "group_members": group_members,
        }

        snapshot = AccessSnapshotDB(
            provider=PROVIDER,
            captured_at=datetime.now(UTC),
            captured_by=captured_by,
            data_version=COLLECTOR_VERSION,
            source_metadata=self._build_source_metadata(run_mode),
            data=data,
            summary=self._build_summary(data),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot
