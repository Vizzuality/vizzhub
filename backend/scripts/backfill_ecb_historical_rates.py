"""One-shot backfill of historical ECB exchange rates.

Fetches ``eurofxref-hist.xml`` (daily rates since 1999) and upserts every
(date, currency) pair into ``exchange_rates``. Safe to re-run — uses the same
``ON CONFLICT DO UPDATE`` semantics as the daily job.

Skips currencies whose rate doesn't fit ``Numeric(12, 6)`` (six pre-decimal
digits). Historical data contains a few extinct hyperinflated currencies
(e.g. Romanian leu pre-2005) that overflow. We only need the surviving set.

Usage:
    cd backend && PYTHONPATH=. uv run python scripts/backfill_ecb_historical_rates.py
"""

import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import httpx
import structlog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.models.exchange_rate import ExchangeRateDB
from app.core.services.exchange_rate_service import ECB_NS
from app.database import async_session_maker

logger = structlog.get_logger()

ECB_HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
BATCH_SIZE = 5000


async def main() -> None:
    logger.info("backfill_started", url=ECB_HIST_URL)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(ECB_HIST_URL)
        resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)
    day_cubes = root.findall(".//ecb:Cube/ecb:Cube[@time]", ECB_NS)
    logger.info("backfill_parsed", days=len(day_cubes))

    now = datetime.now(UTC)
    max_rate = Decimal("999999.999999")  # Numeric(12, 6) ceiling
    rows: list[dict] = []
    skipped: dict[str, int] = {}
    for day_cube in day_cubes:
        rate_date = date.fromisoformat(day_cube.attrib["time"])
        for cube in day_cube.findall("ecb:Cube", ECB_NS):
            rate = Decimal(cube.attrib["rate"])
            code = cube.attrib["currency"]
            if rate > max_rate:
                skipped[code] = skipped.get(code, 0) + 1
                continue
            rows.append(
                {
                    "rate_date": rate_date,
                    "currency_code": code,
                    "rate": rate,
                    "fetched_at": now,
                }
            )

    logger.info("backfill_total_rows", rows=len(rows), skipped_by_currency=skipped)

    async with async_session_maker() as db:
        for i in range(0, len(rows), BATCH_SIZE):
            chunk = rows[i : i + BATCH_SIZE]
            stmt = pg_insert(ExchangeRateDB).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_exchange_rates_date_currency",
                set_={"rate": stmt.excluded.rate, "fetched_at": stmt.excluded.fetched_at},
            )
            await db.execute(stmt)
            logger.info("backfill_chunk_inserted", offset=i, count=len(chunk))
        await db.commit()

    logger.info("backfill_completed")


if __name__ == "__main__":
    asyncio.run(main())
