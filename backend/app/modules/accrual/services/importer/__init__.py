"""Accrual importer helpers retained for the one-time line seed.

The legacy 5-phase import pipeline has been retired (VizzHub is now the source
of truth). What remains are the pure parsing/matching helpers and period
bootstrapping that ``line_seed`` and the period scripts still rely on.
"""

from app.modules.accrual.services.importer.matcher import (
    index_projects,
    resolve_candidates,
)
from app.modules.accrual.services.importer.parser import (
    SpreadsheetRow,
    _code_prefix,
    _normalize_code,
    consolidate_duplicate_rows,
    parse_spreadsheet,
)
from app.modules.accrual.services.importer.periods import (
    bootstrap_periods,
    freeze_historical_periods,
)

__all__ = [
    "SpreadsheetRow",
    "_code_prefix",
    "_normalize_code",
    "bootstrap_periods",
    "consolidate_duplicate_rows",
    "freeze_historical_periods",
    "index_projects",
    "parse_spreadsheet",
    "resolve_candidates",
]
