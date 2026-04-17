"""Devstack module router — aggregates all devstack sub-routers."""

from fastapi import APIRouter

from app.modules.devstack.api import entries as entries_router
from app.modules.devstack.api import prefs as prefs_router

router = APIRouter()

# Static-path routes MUST be registered before CRUD routes
# whose /{entry_id} would swallow "/me"
router.include_router(prefs_router.router, tags=["devstack:prefs"])
router.routes.extend(entries_router.router.routes)
