"""Shared constants for the tracker module."""

from decimal import Decimal

DEFAULT_RATE = Decimal("175.00")

# Legacy ``ProjectDB.currency`` values (`"dollar"`, `"euro"`) mapped to
# canonical ISO-4217 codes. Used by any query that needs to join against
# ``exchange_rates`` until the data is migrated (see `core/models/project.py`).
LEGACY_CURRENCY_TO_ISO: dict[str, str] = {
    "dollar": "USD",
    "euro": "EUR",
}

# Valid axes the aggregation service accepts for ``group_by``.
ALLOWED_GROUP_BY: frozenset[str] = frozenset({"functional_area", "user", "functional_area_user"})

