"""Accrual importer: 5-phase pipeline + supporting helpers.

Public entry-point: ``run_pipeline``. The pipeline takes parsed Excel rows and
applies them to the DB, emitting drift findings and stamping an
``accrual_import_run`` audit row.

Legacy names (``import_projects``, ``parse_spreadsheet``, etc.) are re-exported
here for backward compatibility with existing tests / scripts.
"""

from app.modules.accrual.services.importer.cells import (
    apply_excel_overrides,
    apply_multi_project,
    apply_single_project,
    cell_in_range,
)
from app.modules.accrual.services.importer.drift import detect_drift
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
from app.modules.accrual.services.importer.pipeline import import_projects, run_pipeline
from app.modules.accrual.services.importer.snapshot import snapshot_excel_rows

__all__ = [
    "SpreadsheetRow",
    "_code_prefix",
    "_normalize_code",
    "apply_excel_overrides",
    "apply_multi_project",
    "apply_single_project",
    "bootstrap_periods",
    "cell_in_range",
    "consolidate_duplicate_rows",
    "detect_drift",
    "freeze_historical_periods",
    "import_projects",
    "index_projects",
    "parse_spreadsheet",
    "resolve_candidates",
    "run_pipeline",
    "snapshot_excel_rows",
]
