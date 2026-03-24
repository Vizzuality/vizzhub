"""Playbook module router — aggregates all playbook sub-routers."""

from fastapi import APIRouter

from app.modules.playbook.api import assets as assets_router
from app.modules.playbook.api import nodes as nodes_router
from app.modules.playbook.api import pages as pages_router

router = APIRouter()

router.include_router(nodes_router.router, tags=["playbook:nodes"])
router.include_router(pages_router.router, prefix="/pages", tags=["playbook:pages"])
router.include_router(assets_router.router, prefix="/assets", tags=["playbook:assets"])
