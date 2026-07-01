"""Response schemas for the portfolio analytics dashboard (F1, read-only)."""

from pydantic import BaseModel


class YearVolume(BaseModel):
    """Number of projects active in a given calendar year."""

    year: int
    count: int


class ClientSpend(BaseModel):
    """Total EUR spend attributed to one client (sum of project total_cost in EUR)."""

    client_id: str
    client_name: str
    spend_eur: float
    project_count: int


class MarginSplit(BaseModel):
    """Gain/Loss tally. ``gain`` = margin >= 0 (burn <= 100); ``loss`` = margin < 0
    (burn > 100); ``no_data`` = burn_percentage is None (excluded from avg_margin)."""

    gain: int
    loss: int
    no_data: int
    avg_margin: float | None


class TermCount(BaseModel):
    """One taxonomy term and how many entities carry it."""

    term_name: str
    count: int


class TermBreakdown(BaseModel):
    """A taxonomy and the counts of its terms across entities (bar of mentions)."""

    taxonomy_slug: str
    taxonomy_name: str
    terms: list[TermCount]


class PortfolioKpis(BaseModel):
    """Headline figures for the selected scope (all-time, or a single year)."""

    project_count: int
    total_spend_eur: float
    client_count: int
    avg_margin: float | None


class PortfolioDashboardSummary(BaseModel):
    """Full payload for GET /api/portfolio/dashboard/summary."""

    year: int | None
    available_years: list[int]
    kpis: PortfolioKpis
    volume_by_year: list[YearVolume]
    spend_by_client: list[ClientSpend]
    margin_split: MarginSplit
    breakdowns: list[TermBreakdown]
