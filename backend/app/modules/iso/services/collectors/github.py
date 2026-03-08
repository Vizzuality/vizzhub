"""GitHub collector for ISO access snapshots."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

logger = logging.getLogger(__name__)

BASE_URL = "https://api.github.com"
COLLECTOR_VERSION = "2"
PROVIDER = "github"
REQUIRED_SCOPES = ["read:org"]
API_VERSION = "2022-11-28"
ORG_SETTING_KEY = "iso_org_name"


class GitHubCollector:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._client: httpx.AsyncClient | None = None
        self._org: str | None = None

    async def _paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> list[dict[str, Any]]:
        params = dict(params) if params else {}
        params.setdefault("per_page", 100)
        items: list[dict[str, Any]] = []
        url: str | None = path

        while url:
            response = await self._client.get(url, params=params if url == path else None)

            if optional and response.status_code == 403:
                logger.warning("GitHub 403 on %s — skipping (insufficient permissions)", path)
                return []

            response.raise_for_status()

            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                logger.debug("GitHub rate limit remaining: %s", remaining)

            data = response.json()
            if isinstance(data, list):
                items.extend(data)
            else:
                break

            url = self._parse_next_link(response.headers.get("Link", ""))

        return items

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None

    async def _fetch_user_profile(self, login: str) -> dict[str, str | None]:
        response = await self._client.get(f"/users/{login}")
        if response.status_code != 200:
            return {"name": None, "email": None}
        data = response.json()
        return {
            "name": data.get("name"),
            "email": data.get("email"),
        }

    async def collect_members(self) -> list[dict[str, Any]]:
        admins = await self._paginate(
            f"/orgs/{self._org}/members", {"role": "admin"}, optional=True
        )
        admin_logins = {m["login"] for m in admins}

        all_members = await self._paginate(f"/orgs/{self._org}/members")
        members = []
        for m in all_members:
            profile = await self._fetch_user_profile(m["login"])
            members.append({
                "login": m["login"],
                "id": m["id"],
                "name": profile["name"],
                "email": profile["email"],
                "role": "admin" if m["login"] in admin_logins else "member",
            })
        return members

    async def collect_teams(self) -> list[dict[str, Any]]:
        raw = await self._paginate(f"/orgs/{self._org}/teams", optional=True)
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "slug": t["slug"],
                "parent_slug": t.get("parent", {}).get("slug") if t.get("parent") else None,
                "description": t.get("description", ""),
                "privacy": t.get("privacy", ""),
            }
            for t in raw
        ]

    async def collect_team_members(
        self, teams: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        members: dict[str, list[dict[str, Any]]] = {}
        for team in teams:
            slug = team["slug"]
            maintainers = await self._paginate(
                f"/orgs/{self._org}/teams/{slug}/members", {"role": "maintainer"},
                optional=True,
            )
            maintainer_logins = {m["login"] for m in maintainers}

            all_team = await self._paginate(
                f"/orgs/{self._org}/teams/{slug}/members", optional=True
            )
            members[slug] = [
                {
                    "login": m["login"],
                    "role": "maintainer" if m["login"] in maintainer_logins else "member",
                }
                for m in all_team
            ]
        return members

    async def collect_outside_collaborators(self) -> list[dict[str, Any]]:
        raw = await self._paginate(
            f"/orgs/{self._org}/outside_collaborators", optional=True
        )
        collaborators = []
        for c in raw:
            profile = await self._fetch_user_profile(c["login"])
            collaborators.append({
                "login": c["login"],
                "id": c["id"],
                "name": profile["name"],
                "email": profile["email"],
            })
        return collaborators

    def _build_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        members = data["members"]
        return {
            "total_members": len(members),
            "total_admins": sum(1 for m in members if m["role"] == "admin"),
            "total_teams": len(data["teams"]),
            "outside_collaborators": len(data["outside_collaborators"]),
        }

    def _build_source_metadata(self, run_mode: str) -> dict[str, Any]:
        return {
            "org": self._org,
            "collector": "github",
            "collector_version": COLLECTOR_VERSION,
            "scopes": REQUIRED_SCOPES,
            "run_mode": run_mode,
        }

    async def capture(
        self,
        captured_by: UUID | None = None,
        run_mode: str = "manual",
    ) -> AccessSnapshotDB:
        token = await IntegrationTokenService.get_token(self.db, PROVIDER)
        if not token:
            raise ValueError("GitHub token not configured")

        org_name = await IntegrationTokenService.get_setting(
            self.db, PROVIDER, ORG_SETTING_KEY
        )
        if not org_name:
            raise ValueError("GitHub organization name not configured")

        self._org = org_name

        async with httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
            },
            timeout=30.0,
        ) as client:
            self._client = client

            members = await self.collect_members()
            teams = await self.collect_teams()
            team_members = await self.collect_team_members(teams)
            outside_collaborators = await self.collect_outside_collaborators()

        data = {
            "members": members,
            "teams": teams,
            "team_members": team_members,
            "outside_collaborators": outside_collaborators,
        }

        snapshot = AccessSnapshotDB(
            provider=PROVIDER,
            captured_at=datetime.now(timezone.utc),
            captured_by=captured_by,
            data_version="2",
            source_metadata=self._build_source_metadata(run_mode),
            data=data,
            summary=self._build_summary(data),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot
