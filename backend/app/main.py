import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api import admin_users as admin_users_router
from app.api import auth as auth_router
from app.api import capture as capture_router
from app.api import collectors as collectors_router
from app.api import config as config_router
from app.modules.scorecard.router import router as scorecard_router
from app.api import global_metrics as global_metrics_router
from app.api import jobs as jobs_router
from app.api import metrics as metrics_router
from app.api import oauth as oauth_router
from app.api import projects as projects_router
from app.api import scores as scores_router
from app.api.notifications import router as notifications_router
from app.api.scheduled_jobs import router as scheduled_jobs_router
from app.api.silences import router as silences_router
from app.api.slack_admin import (
    alerts_router as slack_alerts_router,
    router as slack_router,
    templates_router as slack_templates_router,
)
from app.modules.iso.router import router as iso_router
from app.api.deps import limiter
from app.config import get_settings, load_scoring_config_from_db
from app.core.error_handler import ValidationErrorHandler
from app.core.security_middleware import SecurityHeadersMiddleware
from app.database import init_db
from scripts.seed_alert_definitions import seed_alert_definitions
from scripts.seed_config_parameters import seed_config_parameters

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Security warning for development mode
    if settings.debug:
        logger.warning("=" * 80)
        logger.warning("SECURITY WARNING: Running in DEBUG mode")
        logger.warning("Authentication is BYPASSED for requests without tokens")
        logger.warning("This is ONLY for development - DO NOT use in production")
        logger.warning("Production will use Google OAuth (Google Sign-In)")
        logger.warning("=" * 80)

    await init_db()

    # Seed config parameters and alert definitions from CSV if not already seeded
    await seed_config_parameters()
    await seed_alert_definitions()

    # Load scoring config from database into memory
    await load_scoring_config_from_db()
    logger.info("Scoring configuration loaded from database")

    # Initialize Redis score cache (optional — graceful degradation if unavailable)
    redis_client = None
    score_cache = None
    if settings.redis_host:
        from app.services.score_cache import create_score_cache

        redis_client, score_cache = await create_score_cache(
            settings.redis_host, settings.redis_port, settings.redis_password,
        )
        if score_cache:
            logger.info("Redis score cache initialized")

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
    # Log full details server-side
    logger.error(f"Validation error on {request.method} {request.url}")
    logger.error(f"Errors: {exc.errors()}")

    # Use centralized error handler to format message
    message = ValidationErrorHandler.format_pydantic_error(exc)

    # Return user-friendly error response
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,  # Use 400 instead of 422 for consistency
        content={
            "detail": {
                "error": "Validation Error",
                "message": message,
                "type": "validation_error",
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors with sanitized responses."""
    # Log full exception server-side
    logger.exception(f"Unexpected error on {request.method} {request.url}")

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


app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_users_router.router, prefix="/api")
app.include_router(projects_router.router, prefix="/api/projects", tags=["projects"])
app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(scores_router.router, prefix="/api/scores", tags=["scores"])
app.include_router(config_router.router, prefix="/api/config", tags=["config"])
app.include_router(oauth_router.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(
    collectors_router.router, prefix="/api/collect", tags=["collectors"]
)
app.include_router(
    capture_router.router, prefix="/api/projects", tags=["capture"]
)
app.include_router(jobs_router.router, prefix="/api")
app.include_router(global_metrics_router.router, prefix="/api", tags=["global"])
app.include_router(slack_router, prefix="/api")
app.include_router(slack_alerts_router, prefix="/api")
app.include_router(slack_templates_router, prefix="/api")
app.include_router(silences_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(scheduled_jobs_router, prefix="/api")
app.include_router(scorecard_router, prefix="/api", tags=["scorecard"])
app.include_router(iso_router, prefix="/api/iso", tags=["iso"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint - no authentication required."""
    return {"status": "healthy"}
