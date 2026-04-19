"""DevStack data access — catalog entries, tech radar, installables."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryResponse
from app.modules.devstack.services.github_sha import fetch_github_content

logger = structlog.get_logger()

_CATALOG_FIELDS = frozenset((
    "name", "description", "type", "install_method", "url",
    "package", "package_version", "latest_package_version",
    "required", "origin", "tech", "github_sha", "featured",
    "install_count", "last_installed_at",
    "deprecated", "deprecation_message", "vulnerabilities",
))

_DISCOVER_FIELDS = frozenset(("name", "type", "description"))

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


_TARGET_PATH_BY_TYPE = {
    "skill": "~/.claude/skills/{name}/SKILL.md",
    "command": "~/.claude/commands/{name}.md",
    "agent": "~/.claude/agents/{name}.md",
}

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_SHA_LINE_RE = re.compile(r"^devstack_sha:.*$", re.MULTILINE)


def _inject_devstack_sha(content: str, sha: str) -> str:
    """Inject or replace `devstack_sha` in the YAML frontmatter of content.

    Preserves existing formatting. If no frontmatter exists, prepends one.
    """
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return f"---\ndevstack_sha: {sha}\n---\n\n{content}"

    block = match.group(1)
    rest = content[match.end():]
    new_block, count = _SHA_LINE_RE.subn(f"devstack_sha: {sha}", block, count=1)
    if count == 0:
        new_block = f"{block}\ndevstack_sha: {sha}"
    return f"---\n{new_block}\n---\n{rest}"


class InstallableError(Exception):
    """Raised when an entry cannot be installed via get_installable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def get_installable(session: AsyncSession, name: str) -> dict:
    """Return target_path + content with `devstack_sha` injected server-side.

    Raises InstallableError on any problem. Only supports github-installed
    skills, commands, and agents.
    """
    result = await session.execute(
        select(DevstackEntryDB).where(
            DevstackEntryDB.name == name,
            DevstackEntryDB.active.is_(True),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise InstallableError("NOT_FOUND", f"No active catalog entry named {name!r}")

    target_template = _TARGET_PATH_BY_TYPE.get(entry.type)
    if target_template is None:
        raise InstallableError(
            "UNSUPPORTED_TYPE",
            f"Entry type {entry.type!r} is not installable via this tool",
        )

    if entry.install_method != "github" or not entry.url:
        raise InstallableError(
            "NO_GITHUB_URL",
            f"Entry {name!r} does not have a GitHub source URL",
        )

    if not entry.github_sha:
        raise InstallableError(
            "NO_SHA",
            f"Entry {name!r} has no github_sha yet — catalog refresh pending",
        )

    token = await IntegrationTokenService.get_token(session, "github")
    content = await fetch_github_content(entry.url, token)
    if content is None:
        raise InstallableError(
            "FETCH_FAILED",
            f"Could not fetch source for {name!r} from GitHub",
        )

    return {
        "target_path": target_template.format(name=entry.name),
        "content": _inject_devstack_sha(content, entry.github_sha),
    }


async def track_install(name: str) -> None:
    """Fire-and-log: bump install_count + last_installed_at for an active entry.

    Opens its own write session (the read session is postgresql_readonly).
    Any DB error is logged and swallowed — install must not block on tracking.
    """
    from mcp_server.data.base import get_write_session  # noqa: PLC0415 — avoid cycle

    try:
        async with get_write_session() as session:
            await session.execute(
                update(DevstackEntryDB)
                .where(
                    DevstackEntryDB.name == name,
                    DevstackEntryDB.active.is_(True),
                )
                .values(
                    install_count=DevstackEntryDB.install_count + 1,
                    last_installed_at=datetime.now(timezone.utc),
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("devstack_install_counter_failed", name=name, error=str(exc))
