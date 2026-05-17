"""ECB exchange rate fetching and lookup."""

from datetime import UTC, date, datetime
from decimal import Decimal
from xml.etree import ElementTree

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.exchange_rate import ExchangeRateDB

logger = structlog.get_logger()

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
    """Normalize a free-form currency string to its 3-letter ISO 4217 code.

    Accepts legacy human labels (e.g. ``"dollar"``) via ``CURRENCY_NAME_MAP``
    and otherwise upper-cases the input as a passthrough.
    """
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
    now = datetime.now(UTC)

    rows = []
    for cube in cube_parent.findall("ecb:Cube", ECB_NS):
        code = cube.attrib["currency"]
        rate = Decimal(cube.attrib["rate"])
        rows.append(
            {
                "rate_date": rate_date,
                "currency_code": code,
                "rate": rate,
                "fetched_at": now,
            }
        )

    if not rows:
        raise ValueError("ECB XML contained no currency rows")

    stmt = pg_insert(ExchangeRateDB).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_exchange_rates_date_currency",
        set_={"rate": stmt.excluded.rate, "fetched_at": stmt.excluded.fetched_at},
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("ecb_rates_stored", count=len(rows), rate_date=str(rate_date))
    return {"rate_date": str(rate_date), "currencies_stored": len(rows)}


async def get_latest_rate(
    db: AsyncSession,
    currency_code: str | None,
    as_of: date | None = None,
) -> tuple[Decimal, date] | None:
    """Get the most recent rate for a currency on or before ``as_of``.

    When ``as_of`` is None, returns the absolute latest stored rate. When
    ``as_of`` is set, filters ``rate_date <= as_of`` so historical conversions
    (e.g. tracker reports dated months ago) use the rate effective then.

    Returns ``(rate, rate_date)`` or ``None`` when no rate is available. A
    None/empty ``currency_code`` is treated as missing (returns None + warning),
    matching the missing-rate semantics rather than raising.
    """
    if not currency_code:
        logger.warning("exchange_rate_missing_code", as_of=str(as_of) if as_of else None)
        return None

    if currency_code == "EUR":
        return (Decimal("1.0"), as_of or date.today())

    stmt = select(ExchangeRateDB.rate, ExchangeRateDB.rate_date).where(
        ExchangeRateDB.currency_code == currency_code
    )
    if as_of is not None:
        stmt = stmt.where(ExchangeRateDB.rate_date <= as_of)
    stmt = stmt.order_by(ExchangeRateDB.rate_date.desc()).limit(1)

    result = await db.execute(stmt)
    row = result.first()
    return (row.rate, row.rate_date) if row else None


async def convert_to_eur(
    db: AsyncSession,
    amount: Decimal,
    currency: str | None,
    as_of: date | None = None,
) -> Decimal | None:
    """Convert an amount to EUR using the rate effective on or before ``as_of``.

    ``as_of=None`` keeps legacy behaviour (use the latest stored rate). When
    set, looks up the most recent rate with ``rate_date <= as_of`` so historical
    conversions are stable across re-runs.

    Returns ``None`` (with a warning log) for any of:
    - missing/empty currency code (was ``AttributeError`` on ``.lower()``)
    - no rate found for the currency
    - stored rate is zero (was ``decimal.DivisionByZero``)
    """
    if not currency:
        logger.warning("exchange_rate_missing_code", amount=str(amount))
        return None

    code = currency_to_code(currency)
    if code == "EUR":
        return amount

    result = await get_latest_rate(db, code, as_of=as_of)
    if result is None:
        logger.warning(
            "exchange_rate_missing",
            currency=code,
            amount=str(amount),
            as_of=str(as_of) if as_of else None,
        )
        return None

    rate, _ = result
    if rate == 0:
        logger.warning("exchange_rate_zero", currency=code, amount=str(amount))
        return None
    return amount / rate


async def get_available_currencies(db: AsyncSession) -> list[str]:
    """Return all currency codes that have at least one rate stored."""
    result = await db.execute(
        select(ExchangeRateDB.currency_code).distinct().order_by(ExchangeRateDB.currency_code)
    )
    codes = [row[0] for row in result.all()]
    if "EUR" not in codes:
        codes.insert(0, "EUR")
    return codes
