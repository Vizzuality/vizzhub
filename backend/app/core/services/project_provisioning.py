"""Provision a project's accrual artefacts after it is persisted.

Core owns where the datum lands (``project.budget`` in the projects table); the
FX arithmetic and the accrual line are accrual's domain, reached read-only +
write-by-owner through ``accrual.public``. This module holds NO conversion math
(framing invariant, guarded by test).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual import public as accrual_public

logger = structlog.get_logger()


@dataclass
class ProvisionResult:
    budget_changed: bool
    line_id: UUID | None


async def provision_project_accrual(db: AsyncSession, *, project: ProjectDB) -> ProvisionResult:
    """Derive ``project.budget`` and upsert its accrual line in the caller's
    transaction. No-op for non-derivable projects (dual régime)."""
    if (
        project.original_budget is None
        or not project.currency
        or project.start_date is None
        or project.end_date is None
    ):
        return ProvisionResult(budget_changed=False, line_id=None)

    line = await accrual_public.upsert_derived_line(db, project_id=project.id)
    if line is not None:
        new_budget = Decimal(line.value_eur)
    else:
        new_budget = await accrual_public.convert_original_budget(
            db,
            original_budget=Decimal(project.original_budget),
            currency=project.currency,
            start_date=project.start_date,
        )
        if new_budget is None:
            return ProvisionResult(budget_changed=False, line_id=None)

    budget_changed = project.budget != new_budget
    project.budget = new_budget
    logger.info(
        "project_accrual_provisioned",
        project_id=str(project.id),
        budget=str(new_budget),
        budget_changed=budget_changed,
        line_id=str(line.id) if line else None,
    )
    return ProvisionResult(budget_changed=budget_changed, line_id=line.id if line else None)
