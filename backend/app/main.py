from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import config as config_router
from app.api import metrics as metrics_router
from app.api import projects as projects_router
from app.api import scores as scores_router
from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    await init_db()
    yield


app = FastAPI(
    title="Project Scorecard API",
    description="API for evaluating software development projects across 8 dimensions",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router.router, prefix="/api/projects", tags=["projects"])
app.include_router(metrics_router.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(scores_router.router, prefix="/api/scores", tags=["scores"])
app.include_router(config_router.router, prefix="/api/config", tags=["config"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
