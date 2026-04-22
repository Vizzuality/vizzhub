"""Devstack module router — aggregates all devstack sub-routers."""

from fastapi import APIRouter

from app.modules.devstack.api import entries as entries_router

router = APIRouter()

router.routes.extend(entries_router.router.routes)
