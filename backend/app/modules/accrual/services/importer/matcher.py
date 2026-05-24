"""Code-based matching: Excel row → DB project candidates.

Pure logic, no DB I/O. Indexes are built from the project list, then
``resolve_candidates`` is called per Excel row.
"""

from __future__ import annotations

from collections import defaultdict

from app.modules.accrual.services.importer.parser import (
    SpreadsheetRow,
    _code_prefix,
    _normalize_code,
)


def index_projects(
    projects: list,
) -> tuple[dict[str, list], dict[str, list]]:
    """Index DB projects by normalized full code and by prefix (suffix-stripped).

    Returns ``(by_full, by_prefix)`` where each value is a list because a code
    or prefix can be shared by multiple DB projects (e.g. ``GMV.GRASS`` covers
    MVP + Enhancements). The downstream resolver handles the multi-project case
    via overlap matching.
    """
    by_full: dict[str, list] = defaultdict(list)
    by_prefix: dict[str, list] = defaultdict(list)
    for p in projects:
        if not p.code:
            continue
        norm = _normalize_code(p.code)
        if norm:
            by_full[norm].append(p)
        prefix = _code_prefix(p.code)
        if prefix:
            by_prefix[prefix].append(p)
    return by_full, by_prefix


def resolve_candidates(
    row: SpreadsheetRow,
    by_full: dict[str, list],
    by_prefix: dict[str, list],
) -> list:
    """Return DB projects that match an Excel row.

    Match order:
    1. Exact: row's normalized code = project's normalized code.
    2. Row's code is a project's prefix (e.g. Excel ``HE.OEM1`` → DB ``HE.OEM1.22/26``).
    3. Row's prefix is a project's full code (e.g. Excel ``AFOC.AMVP.24`` → DB ``AFOC.AMVP``).

    All matching projects are returned; the caller decides single vs multi.
    """
    norm = _normalize_code(row.code)
    if not norm:
        return []
    if norm in by_full:
        return list(by_full[norm])
    if norm in by_prefix:
        return list(by_prefix[norm])
    row_prefix = _code_prefix(row.code)
    if row_prefix and row_prefix in by_full:
        return list(by_full[row_prefix])
    return []
