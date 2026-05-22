"""Create project_accrual_cells table.

Revision ID: 079_accrual_cells
Revises: 078_accrual_periods
Create Date: 2026-05-22 00:00:02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "079_accrual_cells"
down_revision: str | None = "078_create_accrual_periods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_accrual_cells",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frozen_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("frozen_eur_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("project_id", "year", "month", name="uq_accrual_cells_project_month"),
    )
    op.create_index("ix_accrual_cells_year_month", "project_accrual_cells", ["year", "month"])
    op.create_index("ix_accrual_cells_project", "project_accrual_cells", ["project_id"])
    op.execute(
        "ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_month_range "
        "CHECK (month BETWEEN 1 AND 12)"
    )
    op.execute(
        "ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_amount_nonneg "
        "CHECK (amount >= 0)"
    )
    op.execute(
        "ALTER TABLE project_accrual_cells ADD CONSTRAINT ck_accrual_cells_frozen_consistency "
        "CHECK ("
        "  (is_frozen = false) OR "
        "  (frozen_at IS NOT NULL AND frozen_rate IS NOT NULL AND frozen_eur_amount IS NOT NULL)"
        ")"
    )


def downgrade() -> None:
    op.drop_index("ix_accrual_cells_project", table_name="project_accrual_cells")
    op.drop_index("ix_accrual_cells_year_month", table_name="project_accrual_cells")
    op.drop_table("project_accrual_cells")
