from contextlib import asynccontextmanager
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings, load_scoring_config_from_db
from app.core.api import admin_assets as admin_assets_router
from app.core.api import admin_users as admin_users_router
from app.core.api import auth as auth_router
from app.core.api import commands as commands_router
from app.core.api import currencies as currencies_router
from app.core.api import functional_areas as functional_areas_router
from app.core.api import health as health_router
from app.core.api import jobs as jobs_router
from app.core.api import oauth as oauth_router
from app.core.api import programs as programs_router
from app.core.api import projects_v2 as projects_v2_router
from app.core.api import rates as rates_router
from app.core.api import users as users_router
from app.core.api.deps import limiter
from app.core.error_handler import ValidationErrorHandler
from app.core.logging_config import configure_logging
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.security_middleware import SecurityHeadersMiddleware
from app.database import async_session_maker, init_db
from app.modules.accrual.router import router as accrual_router
from app.modules.capacity.router import router as capacity_router
from app.modules.devstack.router import router as devstack_router
from app.modules.events.router import router as events_router
from app.modules.iso.router import router as iso_router
from app.modules.iso_docs.router import router as iso_docs_router
from app.modules.notifications.router import router as notifications_router
from app.modules.playbook.router import router as playbook_router
from app.modules.scorecard.router import router as scorecard_router
from app.modules.tracker.router import router as tracker_router

settings = get_settings()

configure_logging(
    log_format=settings.log_format,
    log_level=settings.log_level,
    environment=settings.app_env,
    release=settings.release or None,
)


def _sentry_before_send(
    event: dict,
    hint: dict,
) -> dict | None:
    """Filter out expected HTTP errors from Sentry."""
    if "exc_info" in hint:
        exc = hint["exc_info"][1]
        if hasattr(exc, "status_code") and exc.status_code in (401, 403, 404):
            return None
    return event


if settings.sentry_dsn and settings.app_env != "development":
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.release or None,
        traces_sample_rate=0.2,
        before_send=_sentry_before_send,
        send_default_pii=False,
    )

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    if settings.debug:
        logger.warning("app_debug_mode_enabled")

    if settings.debug:
        await init_db()

    # Validate roles table matches code definitions
    from app.core.models.role import RoleDB
    from app.core.permissions.roles import ROLE_PERMISSIONS
    from app.database import async_session_maker

    async with async_session_maker() as _db:
        _result = await _db.execute(select(RoleDB.name))
        db_roles = {row[0] for row in _result.all()}
        code_roles = set(ROLE_PERMISSIONS.keys())
        missing_in_db = code_roles - db_roles
        extra_in_db = db_roles - code_roles
        if missing_in_db:
            logger.warning("roles_missing_in_db", roles=missing_in_db)
        if extra_in_db:
            logger.warning("roles_extra_in_db", roles=extra_in_db)

    # Load scoring config from database into memory
    await load_scoring_config_from_db()
    logger.info("scoring_config_loaded")

    # Initialize Redis score cache (optional — graceful degradation if unavailable)
    redis_client = None
    score_cache = None
    if settings.redis_host:
        from app.modules.scorecard.services.score_cache import create_score_cache

        redis_client, score_cache = await create_score_cache(
            settings.redis_host,
            settings.redis_port,
            settings.redis_password,
        )
        if score_cache:
            logger.info("redis_score_cache_initialized")

    app.state.score_cache = score_cache

    yield

    if redis_client:
        await redis_client.aclose()


app = FastAPI(
    title="Project Scorecard API",
    description="API for evaluating software development projects across 8 dimensions",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add request ID middleware (outermost — runs first)
app.add_middleware(RequestIDMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add session middleware for OAuth state management
if settings.session_secret_key:
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        same_site="lax",
        https_only=not settings.debug,  # HTTPS only in production
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with user-friendly messages."""
    logger.warning(
        "request_validation_failed",
        method=request.method,
        path=str(request.url.path),
        errors=exc.errors(),
    )

    # Use centralized error handler to format message
    message = ValidationErrorHandler.format_pydantic_error(exc)

    # Flat string detail keeps the response compatible with the
    # `{ detail: string }` shape every frontend form expects. Returning
    # an object here used to crash React on render (issue #31).
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,  # Use 400 instead of 422 for consistency
        content={"detail": message},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors with sanitized responses."""
    logger.exception(
        "request_failed",
        method=request.method,
        path=str(request.url.path),
        error_type=type(exc).__name__,
    )

    # Return generic error to client
    if settings.debug:
        # Development - include error type
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {type(exc).__name__}"},
        )
    else:
        # Production - generic message only
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


app.include_router(admin_assets_router.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_users_router.router, prefix="/api")
app.include_router(users_router.router, prefix="/api")
app.include_router(projects_v2_router.router, prefix="/api/projects", tags=["projects"])
app.include_router(programs_router.router, prefix="/api/programs", tags=["programs"])
app.include_router(oauth_router.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(
    currencies_router.router,
    prefix="/api/currencies",
    tags=["currencies"],
)
app.include_router(
    functional_areas_router.router,
    prefix="/api/functional-areas",
    tags=["functional-areas"],
)
app.include_router(
    rates_router.router,
    prefix="/api/rates",
    tags=["rates"],
)
app.include_router(jobs_router.router, prefix="/api")
app.include_router(scorecard_router, prefix="/api", tags=["scorecard"])
app.include_router(iso_router, prefix="/api/iso", tags=["iso"])
app.include_router(tracker_router, prefix="/api/tracker", tags=["tracker"])
app.include_router(accrual_router, prefix="/api/accrual", tags=["accrual"])
app.include_router(capacity_router, prefix="/api/capacity", tags=["capacity"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(playbook_router, prefix="/api/playbook", tags=["playbook"])
app.include_router(iso_docs_router, prefix="/api/iso-docs", tags=["iso-docs"])
app.include_router(events_router, prefix="/api/events", tags=["events"])
app.include_router(devstack_router, prefix="/api/devstack", tags=["devstack"])
app.include_router(commands_router.router, prefix="/api")

# MCP sub-app (disabled by default; enable via MCP_ENABLED=true + MCP_BASE_URL)
if settings.mcp_enabled and settings.mcp_base_url:
    try:
        from mcp.server.auth.settings import (
            AuthSettings,
            ClientRegistrationOptions,
            RevocationOptions,
        )
        from mcp_server.auth.callback import build_google_oauth_callback
        from mcp_server.auth.provider import VizzHubOAuthProvider
        from mcp_server.auth.token_verifier import VizzHubTokenVerifier
        from mcp_server.data.base import enable_backend_sessions, enable_backend_write_sessions
        from mcp_server.server import create_mcp_server
        from starlette.routing import Route

        provider = VizzHubOAuthProvider(
            session_maker=async_session_maker,
            jwt_secret=settings.jwt_secret_key,
            google_client_id=settings.google_client_id,
            allowed_google_domain=settings.allowed_google_domain,
            base_url=settings.mcp_base_url,
        )
        verifier = VizzHubTokenVerifier(secret_key=settings.jwt_secret_key)

        auth_settings = AuthSettings(
            issuer_url=settings.mcp_base_url,
            resource_server_url=settings.mcp_base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["read"],
                default_scopes=["read"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=["read"],
        )

        from urllib.parse import urlparse

        _mcp_host = urlparse(settings.mcp_base_url).hostname

        mcp_server = create_mcp_server(
            auth_server_provider=provider,
            auth_settings=auth_settings,
            http_mode=True,
            allowed_hosts=[_mcp_host] if _mcp_host else None,
        )

        mcp_starlette = mcp_server.sse_app()

        google_callback = build_google_oauth_callback(
            session_maker=async_session_maker,
            google_client_id=settings.google_client_id,
            google_client_secret=settings.google_client_secret,
            allowed_google_domain=settings.allowed_google_domain,
            base_url=settings.mcp_base_url,
        )
        mcp_starlette.routes.append(
            Route("/oauth/callback", endpoint=google_callback, methods=["GET"])
        )

        enable_backend_sessions()
        enable_backend_write_sessions()

        # Upsert pre-registered OAuth client from env vars
        if settings.mcp_oauth_client_id and settings.mcp_oauth_client_secret:
            import asyncio

            from sqlalchemy import select

            from app.core.models.mcp_oauth import MCPOAuthClientDB

            async def _seed_mcp_oauth_client() -> None:
                async with async_session_maker() as session:
                    existing = await session.execute(
                        select(MCPOAuthClientDB).where(
                            MCPOAuthClientDB.client_id == settings.mcp_oauth_client_id
                        )
                    )
                    if existing.scalar_one_or_none() is None:
                        session.add(
                            MCPOAuthClientDB(
                                client_id=settings.mcp_oauth_client_id,
                                client_secret=settings.mcp_oauth_client_secret,
                                client_info={
                                    "client_name": "claude-code",
                                    "redirect_uris": [],
                                    "grant_types": ["authorization_code", "refresh_token"],
                                    "response_types": ["code"],
                                    "token_endpoint_auth_method": "client_secret_post",
                                },
                            )
                        )
                        await session.commit()
                        logger.info(
                            "mcp_oauth_client_seeded", client_id=settings.mcp_oauth_client_id
                        )

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_seed_mcp_oauth_client())
            except RuntimeError:
                asyncio.run(_seed_mcp_oauth_client())

        app.mount("/mcp", mcp_starlette)

        # RFC 9728 + RFC 8414: the SDK expects OAuth metadata at the domain root
        # (not under /mcp mount). Serve directly — SDK doesn't follow redirects.
        base = settings.mcp_base_url

        @app.get("/.well-known/oauth-protected-resource/{path:path}")
        async def _oauth_resource_metadata(path: str) -> JSONResponse:
            return JSONResponse(
                content={
                    "resource": base,
                    "authorization_servers": [base],
                    "scopes_supported": ["read"],
                    "bearer_methods_supported": ["header"],
                },
                headers={"Cache-Control": "public, max-age=3600"},
            )

        @app.get("/.well-known/oauth-authorization-server/{path:path}")
        async def _oauth_server_metadata(path: str) -> JSONResponse:
            return JSONResponse(
                content={
                    "issuer": base,
                    "authorization_endpoint": f"{base}/authorize",
                    "token_endpoint": f"{base}/token",
                    "registration_endpoint": f"{base}/register",
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code", "refresh_token"],
                    "token_endpoint_auth_methods_supported": [
                        "client_secret_post",
                        "client_secret_basic",
                    ],
                    "revocation_endpoint": f"{base}/revoke",
                    "revocation_endpoint_auth_methods_supported": [
                        "client_secret_post",
                        "client_secret_basic",
                    ],
                    "code_challenge_methods_supported": ["S256"],
                },
                headers={"Cache-Control": "public, max-age=3600"},
            )

        logger.info("mcp_server_mounted", base_url=settings.mcp_base_url)
    except Exception:
        logger.exception("mcp_server_mount_failed")


app.include_router(health_router.router)

# Prometheus HTTP metrics — auto-instruments all routes
from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402

Instrumentator(
    excluded_handlers=["/health/live", "/health/ready", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
