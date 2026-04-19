"""Devstack module router — aggregates all devstack sub-routers."""

from fastapi import APIRouter

from app.modules.devstack.api import entries as entries_router
from app.modules.devstack.api import project_contexts as project_contexts_router

router = APIRouter()

# project_contexts must come before entries so /project-contexts is not swallowed
# by the entries /{entry_id} catch-all route.
router.routes.extend(project_contexts_router.router.routes)
router.routes.extend(entries_router.router.routes)
