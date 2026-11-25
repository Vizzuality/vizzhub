"""Read-only client for the Copper CRM Developer API.

Copper API keys (and its single OAuth scope) grant full write access to the
CRM. This client deliberately exposes read operations only; searches are POST
requests in Copper's API but do not modify anything.
"""

from types import TracebackType
from typing import Any, Self

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService

logger = structlog.get_logger()

COPPER_API_BASE = "https://api.copper.com/developer_api/v1"
COPPER_PROVIDER = "copper"
COPPER_USER_EMAIL_KEY = "user_email"
PAGE_SIZE = 200
MAX_PAGES = 50


class CopperError(Exception):
    """Copper API call failed."""


class CopperAuthError(CopperError):
    """Copper rejected the API key / user email pair."""


class CopperClient:
    def __init__(
        self,
        api_key: str,
        user_email: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=COPPER_API_BASE,
            headers={
                "X-PW-AccessToken": api_key,
                "X-PW-Application": "developer_api",
                "X-PW-UserEmail": user_email,
                "Content-Type": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    @classmethod
    async def from_db(cls, db: AsyncSession) -> Self | None:
        """Build a client from the stored credentials, or None if not configured."""
        api_key = await IntegrationTokenService.get_token(db, COPPER_PROVIDER)
        user_email = await IntegrationTokenService.get_setting(
            db, COPPER_PROVIDER, COPPER_USER_EMAIL_KEY
        )
        if not api_key or not user_email:
            return None
        return cls(api_key, user_email)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        try:
            response = await self._http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            logger.warning("copper_request_failed", path=path, error=type(exc).__name__)
            raise CopperError(f"Copper {path} could not be reached") from exc
        if response.status_code == 401:
            raise CopperAuthError("Copper rejected the API key / user email")
        if response.is_error:
            logger.warning("copper_request_failed", path=path, status=response.status_code)
            raise CopperError(f"Copper {path} returned {response.status_code}")
        return response.json()

    async def _search(self, path: str, filters: dict) -> list[dict]:
        results: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            batch = await self._request(
                "POST", path, {**filters, "page_size": PAGE_SIZE, "page_number": page}
            )
            results.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        return results

    async def get_account(self) -> dict:
        return await self._request("GET", "/account")

    async def list_custom_field_definitions(self) -> list[dict]:
        return await self._request("GET", "/custom_field_definitions")

    async def get_company(self, company_id: int) -> dict:
        return await self._request("GET", f"/companies/{company_id}")

    async def search_companies(self) -> list[dict]:
        return await self._search("/companies/search", {"sort_by": "name"})

    async def search_opportunities(
        self, *, pipeline_stage_ids: list[int], minimum_stage_change_date: int
    ) -> list[dict]:
        return await self._search(
            "/opportunities/search",
            {
                "pipeline_stage_ids": pipeline_stage_ids,
                "minimum_stage_change_date": minimum_stage_change_date,
                "sort_by": "date_modified",
                "sort_direction": "desc",
            },
        )
