"""Read-only database session factory for MCP server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from mcp.server.lowlevel.server import request_ctx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_server.config import get_settings

_engine = None
_session_maker = None

# When set, MCP tools use the backend's engine (HTTP mode) instead of a standalone one.
_backend_read_session_maker: async_sessionmaker | None = None
_backend_write_session_maker: async_sessionmaker | None = None

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


def user_context_from_claims(claims: dict) -> McpUserContext:
    return McpUserContext(
        user_id=claims.get("sub") or "unknown",
        email=claims.get("email") or "",
        roles=claims.get("roles") or [],
        permissions=claims.get("permissions") or [],
    )


def _user_from_http_request() -> McpUserContext | None:
    """Identity of the HTTP request that carried the current MCP message.

    Streamable HTTP runs tool handlers in the session's task, which inherits
    the contextvars of the request that *created* the session. A ContextVar
    set by auth middleware would therefore pin the first token's identity for
    the whole session; the SDK's per-message request context does not.
    """
    try:
        request = request_ctx.get().request
    except LookupError:
        return None
    user = request.scope.get("user") if request is not None else None
    token = getattr(user, "access_token", None)
    if token is None or token.claims is None:
        return None
    return user_context_from_claims(token.claims)


def get_mcp_user() -> McpUserContext:
    """Return the current MCP user context. Raises if not set."""
    ctx = _user_from_http_request() or _mcp_user_context.get()
    if ctx is None:
        raise RuntimeError("MCP user context not set")
    return ctx


def set_mcp_user(ctx: McpUserContext) -> None:
    """Set the MCP user context for the current async task (stdio mode)."""
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


def enable_backend_write_sessions() -> None:
    """Create a writable session maker sharing the backend's engine.

    Called during FastAPI lifespan when MCP runs embedded in the backend
    process. Uses the backend engine directly without readonly restrictions.
    """
    global _backend_write_session_maker
    from app.database import engine  # noqa: PLC0415 — intentional late import

    _backend_write_session_maker = async_sessionmaker(
        engine,
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
async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a writable async session. Commits on success, rolls back on error.

    Priority order:
    1. Test override (override_session context manager) — yields shared session as-is
    2. Backend write session maker (when running embedded via enable_backend_write_sessions)
    3. Standalone engine created from MCP settings (stdio mode) without readonly
    """
    override = _session_override.get()
    if override is not None:
        yield override
        return

    if _backend_write_session_maker is not None:
        async with _backend_write_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return

    settings = get_settings()
    standalone_engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    maker = async_sessionmaker(
        standalone_engine, class_=AsyncSession, expire_on_commit=False,
    )
    try:
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await standalone_engine.dispose()


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
