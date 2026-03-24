"""Playbook module router — aggregates all playbook sub-routers."""

from fastapi import APIRouter

from app.modules.playbook.api import nodes as nodes_router

router = APIRouter()

router.include_router(nodes_router.router, tags=["playbook:nodes"])
