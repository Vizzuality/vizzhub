"""Portfolio leaderboard response schemas (F1 redesign)."""

from pydantic import BaseModel


class ProjectRow(BaseModel):
    project_id: str
    name: str
    client_id: str | None
    client_name: str | None
    margin_pct: float
    profit_eur: float | None
    delay_months: int | None


class ClientRow(BaseModel):
    client_id: str | None
    client_name: str
    project_count: int
    profit_eur: float | None
    margin_pct: float | None
    delay_months: float | None


class ProjectLeaderboard(BaseModel):
    available_years: list[int]
    rows: list[ProjectRow]


class ClientLeaderboard(BaseModel):
    available_years: list[int]
    rows: list[ClientRow]
