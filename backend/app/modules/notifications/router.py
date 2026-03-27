"""Notifications module router — aggregates all notification sub-routers."""

from fastapi import APIRouter

from app.modules.notifications.api import notifications as notifications_router
from app.modules.notifications.api import scheduled_jobs as scheduled_jobs_router
from app.modules.notifications.api import silences as silences_router
from app.modules.notifications.api import slack_admin as slack_admin_router

router = APIRouter()

router.include_router(slack_admin_router.alerts_router)
router.include_router(slack_admin_router.templates_router)
router.include_router(slack_admin_router.custom_router)
router.include_router(silences_router.router)
router.include_router(notifications_router.router)
router.include_router(scheduled_jobs_router.router)
