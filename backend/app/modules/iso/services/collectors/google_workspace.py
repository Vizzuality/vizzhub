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
