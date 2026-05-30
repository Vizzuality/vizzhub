"""Collapse accrual cells to line-only; retire the Excel-import era.

The line model is now the source of truth (VizzHub no longer imports the CEO's
Excel). This migration removes the transitional shim and the import-era tables:

- ``project_accrual_cells`` loses its denormalised ``project_id`` (cells belong
  to a line, which carries its own 0..N project links), gets ``line_id`` promoted
  to NOT NULL, and is renamed to ``accrual_cells``.
- ``accrual_aliases`` and ``accrual_drift_findings`` are dropped — both only fed
  the retired importer (aliases resolved Excel→project; drift compared Excel vs
  tracker). ``accrual_excel_rows`` / ``accrual_import_runs`` are KEPT (the
  one-time line seed still reads them).

Reversible structurally (the dropped tables are recreated empty on downgrade);
the real rollback for prod is the pre-migration RDS snapshot.

Revision ID: 084_accrual_cells_cleanup
Revises: 083_accrual_lines
Create Date: 2026-05-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "084_accrual_cells_cleanup"
down_revision: str | None = "083_accrual_lines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DRIFT_KINDS = (
    "date_extend",
    "date_shrink",
    "value_drift",
    "status_stale",
    "missing_excel",
    "missing_tracker",
)


def upgrade() -> None:
    # 1. Drop any orphan cells that were never keyed to a line (legacy
    #    project-keyed writers, now removed) before enforcing NOT NULL.
    op.execute("DELETE FROM project_accrual_cells WHERE line_id IS NULL")

    # 2. Drop the denormalised project_id (the line owns the project links now).
    #    Dropping the column also drops its FK constraint in Postgres.
    op.drop_index("ix_accrual_cells_project", table_name="project_accrual_cells")
    op.drop_column("project_accrual_cells", "project_id")

    # 3. line_id is now mandatory — every cell belongs to a line.
    op.alter_column("project_accrual_cells", "line_id", nullable=False)

    # 4. Rename to its canonical name (constraints/indexes already use the
    #    ``accrual_cells`` prefix, so they stay consistent after the rename).
    op.rename_table("project_accrual_cells", "accrual_cells")

    # 5. Drop the import-era tables (fed only the retired importer).
    op.drop_table("accrual_drift_findings")
    op.drop_table("accrual_aliases")


def downgrade() -> None:
    # Recreate the import-era tables (empty — data is not restored).
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
    op.create_index("ix_accrual_drift_findings_kind", "accrual_drift_findings", ["kind"])
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

    # Reverse the cell-table changes.
    op.rename_table("accrual_cells", "project_accrual_cells")
    op.alter_column("project_accrual_cells", "line_id", nullable=True)
    op.add_column(
        "project_accrual_cells",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_accrual_cells_project", "project_accrual_cells", ["project_id"])
