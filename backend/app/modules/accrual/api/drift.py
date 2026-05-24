"""HTTP endpoints for accrual drift findings.

All routes are mounted under ``/admin/accrual/drift`` and require
``ACCRUAL_MANAGE``. Drift findings are admin-only — they expose information
about how Excel diverges from tracker state and are not consumed by end users.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB, DriftKind
from app.modules.accrual.schemas.drift_finding import (
    DriftFinding,
    DriftFindingsResponse,
    DriftResolveRequest,
    DriftSummaryBucket,
    DriftSummaryResponse,
)
from app.modules.accrual.services import drift_service

logger = structlog.get_logger()
router = APIRouter()

AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]

_VALID_KINDS = {k.value for k in DriftKind}


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


def _serialize(
    finding: AccrualDriftFindingDB,
    project_name: str | None = None,
    project_code: str | None = None,
) -> DriftFinding:
    return DriftFinding(
        id=finding.id,
        kind=finding.kind,
        project_id=finding.project_id,
        project_name=project_name,
        project_code=project_code,
        excel_code=finding.excel_code,
        detected_at=finding.detected_at,
        resolved_at=finding.resolved_at,
        resolution=finding.resolution,
        resolved_by=finding.resolved_by,
        payload=finding.payload or {},
        import_run_id=finding.import_run_id,
    )


@router.get(
    "",
    response_model=DriftFindingsResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_drift_findings(
    _user: AccrualManager,
    db: DBSession,
    kind: Annotated[list[str] | None, Query()] = None,
    resolved: Annotated[bool | None, Query()] = None,
    project_id: Annotated[UUID | None, Query()] = None,
    excel_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DriftFindingsResponse:
    """List drift findings. Unresolved first, then most-recent first."""
    if kind:
        invalid = [k for k in kind if k not in _VALID_KINDS]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid kind(s): {invalid}",
            )
    rows, total = await drift_service.list_findings(
        db,
        kinds=kind,
        resolved=resolved,
        project_id=project_id,
        excel_code=excel_code,
        limit=limit,
        offset=offset,
    )
    items = [
        _serialize(
            finding,
            project_name=project.name if project else None,
            project_code=project.code if project else None,
        )
        for finding, project in rows
    ]
    return DriftFindingsResponse(items=items, total=total)


@router.get(
    "/summary",
    response_model=DriftSummaryResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
async def drift_summary(_user: AccrualManager, db: DBSession) -> DriftSummaryResponse:
    """Return counts grouped by kind, split open vs resolved."""
    data = await drift_service.summary(db)
    return DriftSummaryResponse(
        by_kind={k: DriftSummaryBucket(**v) for k, v in data["by_kind"].items()},
        total_open=data["total_open"],
        total_resolved=data["total_resolved"],
    )


@router.post(
    "/{finding_id}/resolve",
    response_model=DriftFinding,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Finding not found"},
    },
)
async def resolve_drift_finding(
    finding_id: UUID,
    payload: DriftResolveRequest,
    user: AccrualManager,
    db: DBSession,
) -> DriftFinding:
    """Mark a finding as resolved with a free-text note.

    Idempotent: overwrites prior resolution if already resolved.
    """
    try:
        finding = await drift_service.resolve(
            db,
            finding_id=finding_id,
            resolution=payload.resolution,
            resolved_by=_parse_user_id(user),
        )
    except drift_service.DriftFindingNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize(finding)


@router.post(
    "/{finding_id}/reopen",
    response_model=DriftFinding,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Finding not found"},
    },
)
async def reopen_drift_finding(
    finding_id: UUID,
    _user: AccrualManager,
    db: DBSession,
) -> DriftFinding:
    """Clear the resolution so the finding shows as open again."""
    try:
        finding = await drift_service.reopen(db, finding_id=finding_id)
    except drift_service.DriftFindingNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize(finding)
