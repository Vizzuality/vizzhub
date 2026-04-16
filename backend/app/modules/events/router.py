"""Events module router — aggregates all events sub-routers."""

from fastapi import APIRouter

from app.modules.events.api import attendees as attendees_router
from app.modules.events.api import events as events_router
from app.modules.events.api import import_events as import_events_router
from app.modules.events.api import options as options_router
from app.modules.events.api import stats as stats_router

router = APIRouter()

# CRUD routes use empty path ("") so they need extend instead of include_router
# (FastAPI rejects include_router with both empty prefix and empty path)
router.routes.extend(events_router.router.routes)
router.include_router(attendees_router.router, tags=["events:attendees"])
router.include_router(stats_router.router, tags=["events:stats"])
router.include_router(options_router.router, tags=["events:options"])
router.include_router(import_events_router.router, tags=["events:import"])
