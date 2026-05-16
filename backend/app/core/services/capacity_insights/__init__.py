"""Analytical capacity-insights queries.

Cross-module JOINs (core tables: users, functional_areas, projects +
tracker tables: reports, report_parts, reporting_periods) live in
``core/services/`` per architecture Rule 4.

The public API stays at ``app.core.services.capacity_insights`` —
the previous module-as-file has been split into per-view submodules
so existing imports keep working.
"""

from ._shared import (
    SHORT_TO_FA_NAME,
    TARGET_FA_MAPPING,
)
from .allocation import get_allocation_users
from .allocation_projects import get_allocation_projects
from .fa_detail import get_capacity_fa_detail, get_reportable_users
from .insights import get_capacity_insights
from .user_detail import get_capacity_user_detail

__all__ = [
    "SHORT_TO_FA_NAME",
    "TARGET_FA_MAPPING",
    "get_allocation_projects",
    "get_allocation_users",
    "get_capacity_fa_detail",
    "get_capacity_insights",
    "get_capacity_user_detail",
    "get_reportable_users",
]
