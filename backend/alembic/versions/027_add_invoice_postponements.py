"""Add invoice_postponements table and drop legacy extended_date.

Revision ID: 027_add_invoice_postponements
Revises: 026_add_exchange_rates
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_add_invoice_postponements"
down_revision: str = "026_add_exchange_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_postponements",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("postponed_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_invoice_postponements_invoice_created",
        "invoice_postponements",
        ["invoice_id", "created_at"],
    )

    op.drop_constraint("ck_invoices_extended_after_due", "invoices", type_="check")
    op.drop_column("invoices", "extended_date")


def downgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("extended_date", sa.Date(), nullable=True),
    )
    op.create_check_constraint(
        "ck_invoices_extended_after_due",
        "invoices",
        "extended_date IS NULL OR due_date IS NULL OR extended_date >= due_date",
    )
    op.drop_index(
        "ix_invoice_postponements_invoice_created",
        table_name="invoice_postponements",
    )
    op.drop_table("invoice_postponements")
