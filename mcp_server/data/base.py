"""Read-only database session factory for MCP server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_server.config import get_settings

_engine = None
_session_maker = None

# When set, MCP tools use the backend's engine (HTTP mode) instead of a standalone one.
_backend_read_session_maker: async_sessionmaker | None = None

# Test override: when set, get_read_session() uses this session
# instead of creating one from the engine.
_session_override: ContextVar[AsyncSession | None] = ContextVar(
    "_session_override", default=None
)


@dataclass(frozen=True)
class McpUserContext:
    """Identity + permissions of the current MCP caller."""

    user_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, action: str) -> bool:
        return "*" in self.permissions or action in self.permissions


FULL_ACCESS = McpUserContext(
    user_id="stdio",
    email="local",
    roles=["admin"],
    permissions=["*"],
)

_mcp_user_context: ContextVar[McpUserContext | None] = ContextVar(
    "_mcp_user_context", default=None,
)


def get_mcp_user() -> McpUserContext:
    """Return the current MCP user context. Raises if not set."""
    ctx = _mcp_user_context.get()
    if ctx is None:
        raise RuntimeError("MCP user context not set")
    return ctx


def set_mcp_user(ctx: McpUserContext) -> None:
    """Set the MCP user context for the current async task."""
    _mcp_user_context.set(ctx)


@asynccontextmanager
async def override_mcp_user(ctx: McpUserContext) -> AsyncGenerator[None, None]:
    """Override the MCP user context for testing."""
    token = _mcp_user_context.set(ctx)
    try:
        yield
    finally:
        _mcp_user_context.reset(token)


def enable_backend_sessions() -> None:
    """Create a read-only session maker sharing the backend's engine.

    Called during FastAPI lifespan when MCP runs embedded in the backend
    process. Reuses the backend's already-configured engine while enforcing
    read-only access at the PostgreSQL level.
    """
    global _backend_read_session_maker
    from app.database import engine  # noqa: PLC0415 — intentional late import

    # execution_options() returns a new engine proxy; the original engine is untouched.
    readonly_engine = engine.execution_options(postgresql_readonly=True)
    _backend_read_session_maker = async_sessionmaker(
        readonly_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    if _session_maker is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            execution_options={"postgresql_readonly": True},
            echo=False,
        )
        _session_maker = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False,
        )
    return _session_maker


def reset_engine() -> None:
    """Reset cached engine and session maker. Used in tests."""
    global _engine, _session_maker
    _engine = None
    _session_maker = None


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-only async session. Never commits.

    Priority order:
    1. Test override (override_session context manager)
    2. Backend engine session maker (when running embedded via enable_backend_sessions)
    3. Standalone engine created from MCP settings (stdio mode)
    """
    override = _session_override.get()
    if override is not None:
        yield override
        return

    if _backend_read_session_maker is not None:
        async with _backend_read_session_maker() as session:
            yield session
            return

    maker = _get_session_maker()
    async with maker() as session:
        yield session


@asynccontextmanager
async def override_session(session: AsyncSession) -> AsyncGenerator[None, None]:
    """Context manager to override the read session for testing.

    Also sets FULL_ACCESS user context when none is set, so
    permission-gated tools work in tests that only override the session.

    Usage in tests:
        async with override_session(db_session):
            result = await client.call_tool("iso_get_registries", {})
    """
    token = _session_override.set(session)
    user_token = None
    if _mcp_user_context.get() is None:
        user_token = _mcp_user_context.set(FULL_ACCESS)
    try:
        yield
    finally:
        _session_override.reset(token)
        if user_token is not None:
            _mcp_user_context.reset(user_token)
