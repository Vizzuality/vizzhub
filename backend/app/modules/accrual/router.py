"""Accrual module router — aggregates sub-routers."""

from fastapi import APIRouter

# Import models to register with Base.metadata
from app.modules.accrual.models import AccrualPeriodDB  # noqa: F401

router = APIRouter()
