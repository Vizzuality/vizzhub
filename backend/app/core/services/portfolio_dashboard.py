"""Portfolio analytics dashboard — cross-module analytical reads (F1, read-only).

Lives in core/services because it JOINs across core (projects, clients, taxonomies)
and reads tracker-derived costs; analytical JOINs belong here per architecture rule 4.
"""

from collections import defaultdict
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.services import exchange_rate_service
from app.modules.portfolio.schemas.dashboard import (
    ClientSpend,
    MarginSplit,
    PortfolioDashboardSummary,
    PortfolioKpis,
    TermBreakdown,
    TermCount,
    YearVolume,
)
from app.modules.tracker.services import aggregation_service

logger = structlog.get_logger()

BREAKDOWN_SLUGS = ("impact-area", "service")


def _end_year(p: ProjectDB) -> int | None:
    if p.start_date is None:
        return None
    return (p.end_date or p.start_date).year


def _active_in_year(p: ProjectDB, year: int) -> bool:
    if p.start_date is None:
        return False
    return p.start_date.year <= year <= _end_year(p)


async def _eur_rates(db: AsyncSession, currencies: set[str]) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {}
    for currency in currencies:
        code = exchange_rate_service.currency_to_code(currency)
        result = await exchange_rate_service.get_latest_rate(db, code)
        if result is not None:
            rates[code] = result[0]
    return rates


def _to_eur(total_cost: float, currency: str | None, rates: dict[str, Decimal]) -> float | None:
    if not total_cost:
        return 0.0
    if currency is None:
        return None
    code = exchange_rate_service.currency_to_code(currency)
    if code == "EUR":
        return total_cost
    rate = rates.get(code)
    if rate is None or rate == 0:
        return None
    return total_cost / float(rate)


async def _breakdowns(db: AsyncSession) -> list[TermBreakdown]:
    tax_rows = (
        (
            await db.execute(
                select(TaxonomyDB)
                .where(TaxonomyDB.slug.in_(BREAKDOWN_SLUGS), TaxonomyDB.is_active.is_(True))
                .order_by(TaxonomyDB.sort_order)
            )
        )
        .scalars()
        .all()
    )
    counts = defaultdict(int)
    rows = await db.execute(
        select(EntityTermDB.taxonomy_id, TaxonomyTermDB.name).join(
            TaxonomyTermDB, TaxonomyTermDB.id == EntityTermDB.term_id
        )
    )
    for taxonomy_id, term_name in rows.all():
        counts[(taxonomy_id, term_name)] += 1
    out: list[TermBreakdown] = []
    for tax in tax_rows:
        terms = [
            TermCount(term_name=name, count=n) for (tid, name), n in counts.items() if tid == tax.id
        ]
        terms.sort(key=lambda t: t.count, reverse=True)
        out.append(TermBreakdown(taxonomy_slug=tax.slug, taxonomy_name=tax.name, terms=terms))
    return out


async def build_portfolio_summary(
    db: AsyncSession, *, year: int | None = None
) -> PortfolioDashboardSummary:
    projects = (
        (
            await db.execute(
                select(ProjectDB).where(
                    ProjectDB.is_billable.is_(True), ProjectDB.is_absence.is_(False)
                )
            )
        )
        .scalars()
        .all()
    )

    # volume_by_year + available_years span ALL candidate projects (trend, not year-scoped).
    volume: dict[int, int] = defaultdict(int)
    for p in projects:
        if p.start_date is None:
            continue
        for y in range(p.start_date.year, _end_year(p) + 1):
            volume[y] += 1
    volume_by_year = [YearVolume(year=y, count=volume[y]) for y in sorted(volume)]
    available_years = sorted(volume)

    in_scope = [p for p in projects if year is None or _active_in_year(p, year)]
    scope_ids = [p.id for p in in_scope]
    summaries = (
        await aggregation_service.get_batch_cost_summaries(db, scope_ids) if scope_ids else {}
    )

    currencies = {s.currency for s in summaries.values() if s.currency}
    rates = await _eur_rates(db, currencies)

    client_ids = {p.client_id for p in in_scope if p.client_id is not None}
    client_names = {}
    if client_ids:
        rows = await db.execute(
            select(ClientDB.id, ClientDB.name).where(ClientDB.id.in_(client_ids))
        )
        client_names = {cid: name for cid, name in rows.all()}

    total_spend = 0.0
    gain = loss = no_data = 0
    margins: list[float] = []
    spend_by_client: dict = defaultdict(lambda: {"spend": 0.0, "count": 0})
    for p in in_scope:
        s = summaries.get(p.id)
        eur = _to_eur(s.total_cost, s.currency, rates) if s else 0.0
        if eur is not None:
            total_spend += eur
        if p.client_id is not None:
            entry = spend_by_client[p.client_id]
            entry["count"] += 1
            if eur is not None:
                entry["spend"] += eur
        burn = s.burn_percentage if s else None
        if burn is None:
            no_data += 1
        else:
            margin = 100 - burn
            margins.append(margin)
            if margin >= 0:
                gain += 1
            else:
                loss += 1

    avg_margin = round(sum(margins) / len(margins), 2) if margins else None
    spend_rows = [
        ClientSpend(
            client_id=str(cid),
            client_name=client_names.get(cid, "—"),
            spend_eur=round(v["spend"], 2),
            project_count=v["count"],
        )
        for cid, v in spend_by_client.items()
    ]
    spend_rows.sort(key=lambda c: c.spend_eur, reverse=True)

    logger.info("portfolio_dashboard_built", year=year, projects=len(in_scope))
    return PortfolioDashboardSummary(
        year=year,
        available_years=available_years,
        kpis=PortfolioKpis(
            project_count=len(in_scope),
            total_spend_eur=round(total_spend, 2),
            client_count=len(client_ids),
            avg_margin=avg_margin,
        ),
        volume_by_year=volume_by_year,
        spend_by_client=spend_rows[:15],
        margin_split=MarginSplit(gain=gain, loss=loss, no_data=no_data, avg_margin=avg_margin),
        breakdowns=await _breakdowns(db),
    )
