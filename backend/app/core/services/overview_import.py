"""Portfolio Overview import: parse xlsx -> staging, match, apply decisions."""

import io
from dataclasses import dataclass
from uuid import UUID

import structlog
from openpyxl import load_workbook
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import PortfolioOverviewStagingDB

logger = structlog.get_logger()

_SHEET = "Categorised"
_HEADER_ROW = 2
_SEPARATOR = "only old projects"

# 1-based column numbers -> field
_COLS = {
    "name": 3,
    "main_partner": 4,
    "on_website": 5,
    "client_type_raw": 6,
    "service_raw": 7,
    "impact_area_raw": 8,
    "topics_raw": 9,
    "objective": 10,
    "short_description": 11,
    "stage": 12,
    "notes": 13,
    "last_update": 14,
    "web_copy": 15,
    "impact_story": 17,
    "client_contact": 18,
}


@dataclass
class StagedRow:
    row_index: int
    name: str
    main_partner: str | None = None
    on_website: bool | None = None
    client_type_raw: str | None = None
    service_raw: str | None = None
    impact_area_raw: str | None = None
    topics_raw: str | None = None
    objective: str | None = None
    short_description: str | None = None
    stage: str | None = None
    notes: str | None = None
    last_update: str | None = None
    web_copy: str | None = None
    impact_story: str | None = None
    client_contact: str | None = None
    is_old_project: bool = False


def _text(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith(".0"):  # openpyxl reads bare years/ints as floats
        s = s[:-2]
    return s or None


def _yesno(value: object) -> bool | None:
    s = _text(value)
    if s is None:
        return None
    return s.lower().startswith("y")


def parse_overview_xlsx(content: bytes) -> list[StagedRow]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb[_SHEET] if _SHEET in wb.sheetnames else wb.active
    rows: list[StagedRow] = []
    old_mode = False
    for idx, cells in enumerate(
        ws.iter_rows(min_row=_HEADER_ROW + 1, values_only=True), start=_HEADER_ROW + 1
    ):

        def col(field: str, _row: tuple = cells) -> object:
            i = _COLS[field] - 1
            return _row[i] if i < len(_row) else None

        name = _text(col("name"))
        if name is None:
            continue
        if _SEPARATOR in name.lower():
            old_mode = True
            continue
        rows.append(
            StagedRow(
                row_index=idx,
                name=name,
                main_partner=_text(col("main_partner")),
                on_website=_yesno(col("on_website")),
                client_type_raw=_text(col("client_type_raw")),
                service_raw=_text(col("service_raw")),
                impact_area_raw=_text(col("impact_area_raw")),
                topics_raw=_text(col("topics_raw")),
                objective=_text(col("objective")),
                short_description=_text(col("short_description")),
                stage=_text(col("stage")),
                notes=_text(col("notes")),
                last_update=_text(col("last_update")),
                web_copy=_text(col("web_copy")),
                impact_story=_text(col("impact_story")),
                client_contact=_text(col("client_contact")),
                is_old_project=old_mode,
            )
        )
    wb.close()
    return rows


async def replace_staging(
    db: AsyncSession, batch_id: UUID, rows: list[StagedRow]
) -> tuple[int, int]:
    await db.execute(delete(PortfolioOverviewStagingDB))
    old = 0
    for r in rows:
        db.add(
            PortfolioOverviewStagingDB(
                import_batch=batch_id,
                row_index=r.row_index,
                name=r.name,
                main_partner=r.main_partner,
                on_website=r.on_website,
                client_type_raw=r.client_type_raw,
                service_raw=r.service_raw,
                impact_area_raw=r.impact_area_raw,
                topics_raw=r.topics_raw,
                objective=r.objective,
                short_description=r.short_description,
                stage=r.stage,
                notes=r.notes,
                last_update=r.last_update,
                web_copy=r.web_copy,
                impact_story=r.impact_story,
                client_contact=r.client_contact,
                is_old_project=r.is_old_project,
            )
        )
        old += 1 if r.is_old_project else 0
    await db.flush()
    logger.info("portfolio_overview_uploaded", batch_id=str(batch_id), rows=len(rows), old=old)
    return len(rows), old
