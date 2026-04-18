"""DevStack data access — catalog entries and tech radar."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryResponse
from app.modules.devstack.services.github_sha import fetch_github_content

_CATALOG_FIELDS = frozenset((
    "name", "description", "type", "install_method", "url",
    "package", "package_version", "latest_package_version",
    "required", "origin", "tech", "github_sha", "featured",
))

_DISCOVER_FIELDS = frozenset(("name", "type", "description"))

TECH_RADAR_FILES = ("development", "devops", "tools-and-libraries", "data-science-gis")

_TECH_RADAR_REPO = "Vizzuality/vizzuality-engineering-handbook"
_TECH_RADAR_BASE = (
    f"https://github.com/{_TECH_RADAR_REPO}/blob/main/decisions/tech-radar"
)


async def get_catalog(session: AsyncSession) -> list[dict]:
    """Return all active devstack catalog entries."""
    result = await session.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()
    return [
        EntryResponse.model_validate(entry).model_dump(include=_CATALOG_FIELDS)
        for entry in entries
    ]


async def discover(
    session: AsyncSession,
    *,
    type_: str | None = None,
    tech: list[str] | None = None,
    featured_only: bool = False,
) -> list[dict]:
    """Return a lightweight catalog view for dev discovery.

    Filters: type (exact match), tech (any-match), featured_only.
    Ordered by featured desc, required desc, name asc.
    Projection: only name, type, description.
    """
    stmt = select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    if type_ is not None:
        stmt = stmt.where(DevstackEntryDB.type == type_)
    if featured_only:
        stmt = stmt.where(DevstackEntryDB.featured.is_(True))
    if tech:
        stmt = stmt.where(
            or_(*(DevstackEntryDB.tech.contains([tag]) for tag in tech))
        )
    stmt = stmt.order_by(
        DevstackEntryDB.featured.desc(),
        DevstackEntryDB.required.desc(),
        DevstackEntryDB.name.asc(),
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()
    return [
        EntryResponse.model_validate(entry).model_dump(include=_DISCOVER_FIELDS)
        for entry in entries
    ]


async def get_tech_radar(session: AsyncSession, file: str) -> str | None:
    """Fetch a Tech Radar markdown file using the backend's GitHub token.

    Returns the markdown content or None on failure.
    """
    token = await IntegrationTokenService.get_token(session, "github")
    url = f"{_TECH_RADAR_BASE}/{file}.md"
    return await fetch_github_content(url, token)
