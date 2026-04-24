"""Events module router — aggregates all events sub-routers."""

from fastapi import APIRouter

from app.modules.events.api import attendees as attendees_router
from app.modules.events.api import events as events_router
from app.modules.events.api import options as options_router
from app.modules.events.api import rsvps as rsvps_router
from app.modules.events.api import stats as stats_router

router = APIRouter()

# Static-path routers MUST be registered before the CRUD router whose
# /{event_id} path parameter would otherwise swallow "stats", "options", etc.
router.include_router(stats_router.router, tags=["events:stats"])
router.include_router(options_router.router, tags=["events:options"])

# CRUD routes use empty path ("") so they need extend instead of include_router
# (FastAPI rejects include_router with both empty prefix and empty path)
router.routes.extend(events_router.router.routes)
router.include_router(attendees_router.router, tags=["events:attendees"])
router.include_router(rsvps_router.router, tags=["events:rsvps"])
