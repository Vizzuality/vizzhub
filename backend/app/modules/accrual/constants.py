"""Constants for the accrual module."""

from decimal import Decimal

# Minimum difference (EUR) for the migration importer to treat a spreadsheet
# cell as an override vs. the uniform split.
OVERRIDE_THRESHOLD_EUR: Decimal = Decimal("1.00")
