import io
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import PortfolioOverviewStagingDB
from app.core.services.overview_import import parse_overview_xlsx, replace_staging


def _make_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Categorised"
    ws.append(["stray", None])  # row 1 (ignored)
    header = [None] * 21
    header[2] = "Name"  # col3 (0-based index 2)
    ws.append(header)  # row 2

    def row(name, ctype=None, old=False):
        r = [None] * 21
        r[2] = name
        r[5] = ctype
        return r

    ws.append(row("Global Forest Watch (GFW)", "NGO"))  # row 3
    ws.append(row("Marxan", "NGO"))  # row 4
    sep = [None] * 21
    sep[2] = "Only old projects from here down"
    ws.append(sep)  # row 5 separator
    ws.append(row("Ancient Thing"))  # row 6 old
    ws.append([None] * 21)  # row 7 empty -> skipped
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_detects_separator_and_skips_empty() -> None:
    rows = parse_overview_xlsx(_make_xlsx())
    names = [(r.name, r.is_old_project) for r in rows]
    assert names == [
        ("Global Forest Watch (GFW)", False),
        ("Marxan", False),
        ("Ancient Thing", True),
    ]
    assert rows[0].client_type_raw == "NGO"


@pytest.mark.asyncio
async def test_replace_staging_counts(db_session: AsyncSession) -> None:
    rows = parse_overview_xlsx(_make_xlsx())
    count, old = await replace_staging(db_session, uuid4(), rows)
    assert count == 3
    assert old == 1
    total = (
        await db_session.execute(select(func.count()).select_from(PortfolioOverviewStagingDB))
    ).scalar_one()
    assert total == 3
