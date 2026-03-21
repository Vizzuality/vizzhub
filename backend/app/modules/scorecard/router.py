"""Scorecard module router — aggregates all scorecard sub-routers."""

from fastapi import APIRouter

from app.modules.scorecard.api import capture as capture_router
from app.modules.scorecard.api import collectors as collectors_router
from app.modules.scorecard.api import config as config_router
from app.modules.scorecard.api import exports as exports_router
from app.modules.scorecard.api import global_metrics as global_metrics_router
from app.modules.scorecard.api import integrations_admin as integrations_admin_router
from app.modules.scorecard.api import metrics as metrics_router
from app.modules.scorecard.api import notifications as notifications_router
from app.modules.scorecard.api import scheduled_jobs as scheduled_jobs_router
from app.modules.scorecard.api import scores as scores_router
from app.modules.scorecard.api import silences as silences_router
from app.modules.scorecard.api import slack_admin as slack_admin_router

router = APIRouter()

router.include_router(metrics_router.router, prefix="/metrics", tags=["metrics"])
router.include_router(scores_router.router, prefix="/scores", tags=["scores"])
router.include_router(config_router.router, prefix="/config", tags=["config"])
router.include_router(collectors_router.router, prefix="/collect", tags=["collectors"])
router.include_router(capture_router.router, prefix="/scorecards", tags=["capture"])
router.include_router(exports_router.router, prefix="/exports", tags=["exports"])

# These routers define their own prefixes internally
router.include_router(global_metrics_router.router)
router.include_router(slack_admin_router.alerts_router)
router.include_router(slack_admin_router.templates_router)
router.include_router(slack_admin_router.custom_router)
router.include_router(integrations_admin_router.router)
router.include_router(silences_router.router)
router.include_router(notifications_router.router)
router.include_router(scheduled_jobs_router.router)
