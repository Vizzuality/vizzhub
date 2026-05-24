"""Drop FX columns now that accrual cells are EUR-only.

Cells are stored directly in EUR (mirroring the CEO's spreadsheet), so:
- projects.locked_fx_rate (per-project override) no longer applies
- accrual_periods.fx_rates (period medians) no longer needed
- project_accrual_cells.frozen_rate (rate locked at close) is redundant —
  frozen_eur_amount holds the value at close and that's all we need.

Revision ID: 081_drop_fx_columns
Revises: 080_original_budget
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "081_drop_fx_columns"
down_revision: str | None = "080_original_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old check constraint that referenced frozen_rate, then recreate
    # it without that field.
    op.execute("ALTER TABLE project_accrual_cells DROP CONSTRAINT ck_accrual_cells_frozen_consistency")
    op.execute(
        "ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_frozen_consistency "
        "CHECK ((is_frozen = false) OR (frozen_at IS NOT NULL AND frozen_eur_amount IS NOT NULL))"
    )
    op.drop_column("project_accrual_cells", "frozen_rate")
    op.drop_column("accrual_periods", "fx_rates")
    op.drop_column("projects", "locked_fx_rate")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("locked_fx_rate", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "accrual_periods",
        sa.Column(
            "fx_rates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "project_accrual_cells",
        sa.Column("frozen_rate", sa.Numeric(12, 6), nullable=True),
    )
    op.execute("ALTER TABLE project_accrual_cells DROP CONSTRAINT ck_accrual_cells_frozen_consistency")
    op.execute(
        "ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_frozen_consistency "
        "CHECK ((is_frozen = false) OR "
        "(frozen_at IS NOT NULL AND frozen_rate IS NOT NULL AND frozen_eur_amount IS NOT NULL))"
    )
