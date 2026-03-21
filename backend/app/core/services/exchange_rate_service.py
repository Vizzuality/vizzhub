"""ECB exchange rate fetching and lookup."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.exchange_rate import ExchangeRateDB

logger = logging.getLogger(__name__)

ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
# XML namespace identifiers (not network URLs — must match ECB's XML declaration)
ECB_NS = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",  # NOSONAR
    "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",  # NOSONAR
}

CURRENCY_NAME_MAP: dict[str, str] = {
    "dollar": "USD",
    "euro": "EUR",
}


def currency_to_code(currency: str) -> str:
    """Map project currency string to ISO code. Passthrough if already a code."""
    return CURRENCY_NAME_MAP.get(currency.lower(), currency.upper())


async def fetch_and_store_rates(db: AsyncSession) -> dict:
    """Fetch today's ECB rates and upsert into DB.

    Returns dict with rate_date, count of currencies stored, or error.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ECB_DAILY_URL)
        resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)
    cube_parent = root.find(".//ecb:Cube/ecb:Cube[@time]", ECB_NS)
    if cube_parent is None:
        raise ValueError("Could not parse ECB XML — missing Cube element")

    rate_date = date.fromisoformat(cube_parent.attrib["time"])
    now = datetime.now(timezone.utc)

    rows = []
    for cube in cube_parent.findall("ecb:Cube", ECB_NS):
        code = cube.attrib["currency"]
        rate = Decimal(cube.attrib["rate"])
        rows.append({
            "rate_date": rate_date,
            "currency_code": code,
            "rate": rate,
            "fetched_at": now,
        })

    if not rows:
        raise ValueError("ECB XML contained no currency rows")

    stmt = pg_insert(ExchangeRateDB).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_exchange_rates_date_currency",
        set_={"rate": stmt.excluded.rate, "fetched_at": stmt.excluded.fetched_at},
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("Stored %d ECB rates for %s", len(rows), rate_date)
    return {"rate_date": str(rate_date), "currencies_stored": len(rows)}


async def get_latest_rate(db: AsyncSession, currency_code: str) -> tuple[Decimal, date] | None:
    """Get the most recent rate for a currency. Returns (rate, rate_date) or None."""
    if currency_code == "EUR":
        return (Decimal("1.0"), date.today())

    result = await db.execute(
        select(ExchangeRateDB.rate, ExchangeRateDB.rate_date)
        .where(ExchangeRateDB.currency_code == currency_code)
        .order_by(ExchangeRateDB.rate_date.desc())
        .limit(1)
    )
    row = result.first()
    return (row.rate, row.rate_date) if row else None


async def convert_to_eur(db: AsyncSession, amount: Decimal, currency: str) -> Decimal | None:
    """Convert an amount to EUR using the latest rate. Returns None if no rate found."""
    code = currency_to_code(currency)
    if code == "EUR":
        return amount

    result = await get_latest_rate(db, code)
    if result is None:
        return None

    rate, _ = result
    return amount / rate


async def get_available_currencies(db: AsyncSession) -> list[str]:
    """Return all currency codes that have at least one rate stored."""
    result = await db.execute(
        select(ExchangeRateDB.currency_code)
        .distinct()
        .order_by(ExchangeRateDB.currency_code)
    )
    codes = [row[0] for row in result.all()]
    if "EUR" not in codes:
        codes.insert(0, "EUR")
    return codes
