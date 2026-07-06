"""Taxonomies read endpoints (core, portfolio:view)."""

from collections import defaultdict
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.models.taxonomy import Taxonomy, TaxonomyDB, TaxonomyTerm, TaxonomyTermDB
from app.core.permissions import Action, require_permission

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]

router = APIRouter()
logger = structlog.get_logger()


@router.get("")
@limiter.limit("100/minute")
async def list_taxonomies(
    request: Request, current_user: PortfolioViewer, db: DBSession
) -> list[Taxonomy]:
    result = await db.execute(
        select(TaxonomyDB)
        .where(TaxonomyDB.is_active.is_(True))
        .order_by(TaxonomyDB.sort_order, TaxonomyDB.name)
    )
    taxonomies = result.scalars().all()
    if not taxonomies:
        return []

    terms_result = await db.execute(
        select(TaxonomyTermDB)
        .where(
            TaxonomyTermDB.taxonomy_id.in_([tax.id for tax in taxonomies]),
            TaxonomyTermDB.is_active.is_(True),
        )
        .order_by(TaxonomyTermDB.sort_order, TaxonomyTermDB.name)
    )
    terms_by_taxonomy: dict[UUID, list[TaxonomyTerm]] = defaultdict(list)
    for term in terms_result.scalars().all():
        terms_by_taxonomy[term.taxonomy_id].append(TaxonomyTerm.model_validate(term))

    out: list[Taxonomy] = []
    for tax in taxonomies:
        model = Taxonomy.model_validate(tax)
        model.terms = terms_by_taxonomy[tax.id]
        out.append(model)
    return out
