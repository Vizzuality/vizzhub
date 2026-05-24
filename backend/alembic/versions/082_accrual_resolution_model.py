"""Persistent resolution model for accrual: Excel rows, aliases, drift findings, import runs.

Adds four tables that decouple "what Excel row maps to what tracker project"
from "how cells are computed":

- accrual_import_run: one row per importer execution (audit trail).
- accrual_excel_row: snapshot of every Excel row parsed (source of truth for Excel side).
- accrual_alias: persistent N:M mapping Excel↔tracker (with weights).
- accrual_drift_finding: divergences (dates, value, status, missing) for human review.

Also adds project_accrual_cells.source so the UI can distinguish Excel-derived
cells from team-budget fallback cells.

Enum-like columns are stored as VARCHAR with CHECK constraints (no PostgreSQL
ENUM types) to avoid the alembic+asyncpg enum gotchas and to keep migrations
trivially reversible.

Revision ID: 082_accrual_resolution
Revises: 081_drop_fx_columns
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "082_accrual_resolution"
down_revision: str | None = "081_drop_fx_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DRIFT_KINDS = ("date_extend", "date_shrink", "value_drift", "status_stale", "missing_excel", "missing_tracker")
CELL_SOURCES = ("excel", "team_budget", "manual")


def upgrade() -> None:
    # 1. accrual_import_run — audit trail per importer execution.
    op.create_table(
        "accrual_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("rows_parsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_mapped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_unmatched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drift_findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "raw_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_accrual_import_runs_started_at",
        "accrual_import_runs",
        ["started_at"],
    )

    # 2. accrual_excel_row — snapshot of every Excel row from the latest parse.
    # `import_run_id` lets us keep historical snapshots; queries against the
    # "current" Excel always filter by the most-recent run.
    op.create_table(
        "accrual_excel_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accrual_import_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("import_run_position", sa.Integer(), nullable=False),
        sa.Column("excel_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("pm_name", sa.Text(), nullable=True),
        sa.Column("client", sa.Text(), nullable=True),
        sa.Column("value_orig", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("rate", sa.Numeric(14, 6), nullable=True),
        sa.Column("value_eur", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("months", sa.Integer(), nullable=True),
        # monthly_cells: list of {year, month, eur_amount} objects.
        sa.Column(
            "monthly_cells",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.UniqueConstraint(
            "import_run_id",
            "excel_code",
            "import_run_position",
            name="uq_accrual_excel_rows_run_code_pos",
        ),
    )
    op.create_index(
        "ix_accrual_excel_rows_import_run",
        "accrual_excel_rows",
        ["import_run_id"],
    )
    op.create_index(
        "ix_accrual_excel_rows_excel_code",
        "accrual_excel_rows",
        ["excel_code"],
    )

    # 3. accrual_alias — persistent N:M mapping Excel↔tracker with weights.
    op.create_table(
        "accrual_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("excel_code", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight", sa.Numeric(6, 4), nullable=False, server_default="1.0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("excel_code", "project_id", name="uq_accrual_aliases_code_project"),
    )
    op.create_index("ix_accrual_aliases_excel_code", "accrual_aliases", ["excel_code"])
    op.create_index("ix_accrual_aliases_project_id", "accrual_aliases", ["project_id"])
    op.execute(
        "ALTER TABLE accrual_aliases ADD CONSTRAINT ck_accrual_aliases_weight_range "
        "CHECK (weight > 0 AND weight <= 1)"
    )

    # 4. accrual_drift_finding — divergences flagged for human review.
    op.create_table(
        "accrual_drift_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("excel_code", sa.Text(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accrual_import_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_accrual_drift_findings_kind", "accrual_drift_findings", ["kind"]
    )
    op.create_index(
        "ix_accrual_drift_findings_project", "accrual_drift_findings", ["project_id"]
    )
    op.create_index(
        "ix_accrual_drift_findings_excel_code", "accrual_drift_findings", ["excel_code"]
    )
    op.create_index(
        "ix_accrual_drift_findings_unresolved",
        "accrual_drift_findings",
        ["detected_at"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    kinds_sql = ", ".join(f"'{k}'" for k in DRIFT_KINDS)
    op.execute(
        f"ALTER TABLE accrual_drift_findings ADD CONSTRAINT ck_accrual_drift_findings_kind "
        f"CHECK (kind IN ({kinds_sql}))"
    )
    op.execute(
        "ALTER TABLE accrual_drift_findings ADD CONSTRAINT ck_accrual_drift_findings_subject "
        "CHECK (project_id IS NOT NULL OR excel_code IS NOT NULL)"
    )

    # 5. project_accrual_cells.source — flag where the cell value came from.
    # Default 'excel' for forward-compat; the new pipeline will set this
    # explicitly. Manual overrides keep 'manual'; team-budget fallback rows
    # get 'team_budget'.
    op.add_column(
        "project_accrual_cells",
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default="excel",
        ),
    )
    sources_sql = ", ".join(f"'{s}'" for s in CELL_SOURCES)
    op.execute(
        f"ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_source "
        f"CHECK (source IN ({sources_sql}))"
    )
    # Backfill: cells with is_manual_override should already be 'manual'.
    op.execute(
        "UPDATE project_accrual_cells SET source = 'manual' "
        "WHERE is_manual_override = true"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE project_accrual_cells DROP CONSTRAINT ck_accrual_cells_source")
    op.drop_column("project_accrual_cells", "source")

    op.drop_index("ix_accrual_drift_findings_unresolved", table_name="accrual_drift_findings")
    op.drop_index("ix_accrual_drift_findings_excel_code", table_name="accrual_drift_findings")
    op.drop_index("ix_accrual_drift_findings_project", table_name="accrual_drift_findings")
    op.drop_index("ix_accrual_drift_findings_kind", table_name="accrual_drift_findings")
    op.drop_table("accrual_drift_findings")

    op.drop_index("ix_accrual_aliases_project_id", table_name="accrual_aliases")
    op.drop_index("ix_accrual_aliases_excel_code", table_name="accrual_aliases")
    op.drop_table("accrual_aliases")

    op.drop_index("ix_accrual_excel_rows_excel_code", table_name="accrual_excel_rows")
    op.drop_index("ix_accrual_excel_rows_import_run", table_name="accrual_excel_rows")
    op.drop_table("accrual_excel_rows")

    op.drop_index("ix_accrual_import_runs_started_at", table_name="accrual_import_runs")
    op.drop_table("accrual_import_runs")
