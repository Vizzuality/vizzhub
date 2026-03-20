"""Move currency from invoices to projects.

Revision ID: 024
Revises: 023
"""

import sqlalchemy as sa
from alembic import op

revision: str = "024_move_currency_to_projects"
down_revision: str = "023_merge_adjusted_days"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate: set project currency from its invoices, default to 'dollar' for NULLs
    op.execute("""
        UPDATE projects p
        SET currency = sub.currency
        FROM (
            SELECT DISTINCT ON (project_id) project_id, currency
            FROM invoices
            WHERE currency IS NOT NULL
            GROUP BY project_id, currency
            ORDER BY project_id, COUNT(*) DESC
        ) sub
        WHERE p.id = sub.project_id
          AND p.currency IS NULL
    """)

    # Default remaining NULL currencies to 'dollar'
    op.execute("UPDATE projects SET currency = 'dollar' WHERE currency IS NULL")

    # Make projects.currency NOT NULL with default
    op.alter_column(
        "projects", "currency",
        nullable=False,
        server_default="dollar",
        existing_type=sa.String(20),
    )

    # Drop the check constraint first, then the column
    op.drop_constraint("ck_invoices_currency_valid", "invoices", type_="check")
    op.drop_column("invoices", "currency")

    # Add check constraint to projects.currency
    op.create_check_constraint(
        "ck_projects_currency_valid",
        "projects",
        "currency IN ('euro', 'dollar')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_currency_valid", "projects", type_="check")
    op.alter_column(
        "projects", "currency",
        nullable=True,
        server_default=None,
        existing_type=sa.String(20),
    )
    op.add_column("invoices", sa.Column("currency", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_invoices_currency_valid",
        "invoices",
        "currency IN ('euro', 'dollar')",
    )
