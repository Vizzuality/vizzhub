import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.api import collectors as collectors_router
from app.api import config as config_router
from app.api import metrics as metrics_router
from app.api import oauth as oauth_router
from app.api import projects as projects_router
from app.api import scores as scores_router
from app.config import get_settings
from app.core.security_middleware import SecurityHeadersMiddleware
from app.database import init_db

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


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
    yield


app = FastAPI(
    title="Project Scorecard API",
    description="API for evaluating software development projects across 8 dimensions",
    version="1.0.0",
    lifespan=lifespan,
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
    """Handle validation errors with sanitized responses."""
    # Log full details server-side
    logger.error(f"Validation error on {request.method} {request.url}")
    logger.error(f"Errors: {exc.errors()}")

    # Return sanitized response based on environment
    if settings.debug:
        # Development - return detailed errors
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )
    else:
        # Production - return generic error
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Invalid request data"},
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


app.include_router(projects_router.router, prefix="/api/projects", tags=["projects"])
app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(scores_router.router, prefix="/api/scores", tags=["scores"])
app.include_router(config_router.router, prefix="/api/config", tags=["config"])
app.include_router(oauth_router.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(
    collectors_router.router, prefix="/api/collect", tags=["collectors"]
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint - no authentication required."""
    return {"status": "healthy"}
