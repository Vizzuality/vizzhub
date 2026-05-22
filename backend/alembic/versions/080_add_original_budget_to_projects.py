"""add original_budget to projects

Revision ID: 080_original_budget
Revises: 079_accrual_cells
"""

from alembic import op
import sqlalchemy as sa

revision = "080_original_budget"
down_revision = "079_accrual_cells"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("original_budget", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "original_budget")
