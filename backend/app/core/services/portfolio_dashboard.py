"""Portfolio leaderboards — cross-module analytical reads (F1 redesign, read-only).

Ranks finished billable projects (and rolls up by client) on margin %, profit €,
and delay months. Lives in core/services because it JOINs core projects/clients
with tracker-derived costs (architecture rule 4). Reads the persisted
projects.finished_at (backfilled effective close) for delay.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services import exchange_rate_service
from app.modules.portfolio.schemas.dashboard import (
    ClientLeaderboard,
    ClientRow,
    ProjectLeaderboard,
    ProjectRow,
)
from app.modules.tracker.services import aggregation_service

logger = structlog.get_logger()

UNASSIGNED = "— Unassigned"


@dataclass
class _ProjectMetric:
    project_id: str
    name: str
    client_id: str | None
    client_name: str | None
    margin_pct: float
    profit_eur: float | None
    budget_eur: float | None
    delay_months: int | None


async def _eur_rates(db: AsyncSession, currencies: set[str]) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {}
    for currency in currencies:
        code = exchange_rate_service.currency_to_code(currency)
        result = await exchange_rate_service.get_latest_rate(db, code)
        if result is not None:
            rates[code] = result[0]
    return rates


def _to_eur(amount: float, currency: str | None, rates: dict[str, Decimal]) -> float | None:
    if currency is None:
        return None
    code = exchange_rate_service.currency_to_code(currency)
    if code == "EUR":
        return amount
    rate = rates.get(code)
    if rate is None or rate == 0:
        return None
    return amount / float(rate)


def _months_between(later, earlier) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


async def _scope(db: AsyncSession) -> list[ProjectDB]:
    return list(
        (
            await db.execute(
                select(ProjectDB).where(
                    ProjectDB.status == "finished",
                    ProjectDB.is_billable.is_(True),
                    ProjectDB.is_absence.is_(False),
                    ProjectDB.budget.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )


async def _collect(db: AsyncSession, year: int | None) -> tuple[list[int], list[_ProjectMetric]]:
    """Shared scope + per-project metrics used by both leaderboards."""
    projects = await _scope(db)
    available_years = sorted({p.finished_at.year for p in projects if p.finished_at is not None})
    in_scope = [
        p
        for p in projects
        if year is None or (p.finished_at is not None and p.finished_at.year == year)
    ]
    summaries = (
        await aggregation_service.get_batch_cost_summaries(db, [p.id for p in in_scope])
        if in_scope
        else {}
    )
    rates = await _eur_rates(db, {s.currency for s in summaries.values() if s.currency})

    client_ids = {p.client_id for p in in_scope if p.client_id is not None}
    client_names: dict = {}
    if client_ids:
        rows = await db.execute(
            select(ClientDB.id, ClientDB.name).where(ClientDB.id.in_(client_ids))
        )
        client_names = dict(rows.all())

    metrics: list[_ProjectMetric] = []
    for p in in_scope:
        s = summaries.get(p.id)
        if s is None or not s.budget:
            continue
        profit = s.budget - s.total_cost
        profit_eur = _to_eur(profit, s.currency, rates)
        budget_eur = _to_eur(s.budget, s.currency, rates)
        delay = (
            _months_between(p.finished_at, p.end_date)
            if p.finished_at is not None and p.end_date is not None
            else None
        )
        metrics.append(
            _ProjectMetric(
                project_id=str(p.id),
                name=p.name,
                client_id=str(p.client_id) if p.client_id else None,
                client_name=client_names.get(p.client_id),
                margin_pct=round(profit / s.budget * 100, 2),
                profit_eur=round(profit_eur, 2) if profit_eur is not None else None,
                budget_eur=budget_eur,
                delay_months=delay,
            )
        )
    return available_years, metrics


async def build_project_leaderboard(
    db: AsyncSession, *, year: int | None = None
) -> ProjectLeaderboard:
    available_years, metrics = await _collect(db, year)
    rows = [
        ProjectRow(
            project_id=m.project_id,
            name=m.name,
            client_id=m.client_id,
            client_name=m.client_name,
            margin_pct=m.margin_pct,
            profit_eur=m.profit_eur,
            delay_months=m.delay_months,
        )
        for m in metrics
    ]
    logger.info("portfolio_project_leaderboard_built", year=year, rows=len(rows))
    return ProjectLeaderboard(available_years=available_years, rows=rows)


def _aggregate_by_client(metrics: list[_ProjectMetric]) -> dict[tuple[str | None, str], dict]:
    agg: dict[tuple[str | None, str], dict] = defaultdict(
        lambda: {"count": 0, "profit_eur": 0.0, "budget_eur": 0.0, "has_eur": False, "delays": []}
    )
    for m in metrics:
        e = agg[(m.client_id, m.client_name or UNASSIGNED)]
        e["count"] += 1
        if m.delay_months is not None:
            e["delays"].append(m.delay_months)
        if m.profit_eur is not None and m.budget_eur:
            e["profit_eur"] += m.profit_eur
            e["budget_eur"] += m.budget_eur
            e["has_eur"] = True
    return agg


def _client_row(cid: str | None, cname: str, e: dict) -> ClientRow:
    margin = (e["profit_eur"] / e["budget_eur"] * 100) if e["budget_eur"] else None
    return ClientRow(
        client_id=cid,
        client_name=cname,
        project_count=e["count"],
        profit_eur=round(e["profit_eur"], 2) if e["has_eur"] else None,
        margin_pct=round(margin, 2) if margin is not None else None,
        delay_months=round(sum(e["delays"]) / len(e["delays"]), 1) if e["delays"] else None,
    )


async def build_client_leaderboard(
    db: AsyncSession, *, year: int | None = None
) -> ClientLeaderboard:
    available_years, metrics = await _collect(db, year)
    agg = _aggregate_by_client(metrics)
    rows = [_client_row(cid, cname, e) for (cid, cname), e in agg.items()]
    logger.info("portfolio_client_leaderboard_built", year=year, rows=len(rows))
    return ClientLeaderboard(available_years=available_years, rows=rows)
