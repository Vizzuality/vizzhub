"""The Cerebro read role sees only what the allowlist names.

Every table and every column of a column-granted table must be classified, so
a new table or column fails here until someone decides whether Cerebro may
read it (and ships a migration for the grant).
"""

from __future__ import annotations

import app.main  # noqa: F401  registers every model on the metadata
from app.core.cerebro_access import (
    COLUMN_GRANTS,
    EXCLUDED_COLUMNS,
    NOT_GRANTED,
    TABLE_GRANTS,
)
from app.database import Base


def test_every_table_is_classified() -> None:
    classified = set(TABLE_GRANTS) | set(COLUMN_GRANTS) | set(NOT_GRANTED)
    unclassified = set(Base.metadata.tables) - classified
    assert not unclassified, f"decide Cerebro access for: {sorted(unclassified)}"


def test_no_table_is_in_two_groups() -> None:
    groups = [set(TABLE_GRANTS), set(COLUMN_GRANTS), set(NOT_GRANTED)]
    for i, a in enumerate(groups):
        for b in groups[i + 1 :]:
            assert not a & b, f"table in two groups: {sorted(a & b)}"


def test_classified_tables_exist() -> None:
    classified = set(TABLE_GRANTS) | set(COLUMN_GRANTS) | set(NOT_GRANTED)
    stale = classified - set(Base.metadata.tables)
    assert not stale, f"classified tables that no longer exist: {sorted(stale)}"


def test_every_column_of_a_column_granted_table_is_classified() -> None:
    for table, granted in COLUMN_GRANTS.items():
        columns = {c.name for c in Base.metadata.tables[table].columns}
        excluded = EXCLUDED_COLUMNS[table]
        assert not set(granted) & set(excluded), f"{table}: column in both lists"
        assert set(granted) | set(excluded) == columns, (
            f"{table}: unclassified {sorted(columns - set(granted) - set(excluded))}, "
            f"unknown {sorted((set(granted) | set(excluded)) - columns)}"
        )


def test_sensitive_data_is_not_granted() -> None:
    for table in (
        "mcp_oauth_refresh_tokens",
        "oauth_tokens",
        "anonymous_feedback",
        "invoices",
        "rates",
        "accrual_cells",
    ):
        assert table in NOT_GRANTED
    assert "rate_id" in EXCLUDED_COLUMNS["users"]
    assert {"mood", "feedback_text"} <= set(EXCLUDED_COLUMNS["reports"])
    assert "cost" in EXCLUDED_COLUMNS["report_parts"]
