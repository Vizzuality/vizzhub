"""Cleanup expired MCP OAuth codes and refresh tokens."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import delete

from app.core.models.mcp_oauth import MCPOAuthCodeDB, MCPOAuthRefreshTokenDB

logger = structlog.get_logger()


async def cleanup_mcp_oauth(ctx: dict) -> None:
    """Purge expired MCP OAuth codes and refresh tokens."""
    db = ctx["db"]
    now = datetime.now(UTC)

    codes_result = await db.execute(delete(MCPOAuthCodeDB).where(MCPOAuthCodeDB.expires_at < now))
    tokens_result = await db.execute(
        delete(MCPOAuthRefreshTokenDB).where(MCPOAuthRefreshTokenDB.expires_at < now)
    )
    await db.commit()

    logger.info(
        "mcp_oauth_cleanup_completed",
        expired_codes=codes_result.rowcount,
        expired_tokens=tokens_result.rowcount,
    )
