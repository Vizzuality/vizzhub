"""Add invoicing contact name and email to invoices.

Part of the invoice UI unification: the detail/overlay is the single
write surface, so we surface the contact who should receive the invoice
as first-class fields instead of stuffing them into observations.
"""

from alembic import op

revision = "074_invoice_contact_fields"
down_revision = "073_devstack_last_fetch_ok_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE invoices "
        "ADD COLUMN IF NOT EXISTS invoicing_contact_name VARCHAR(200)"
    )
    op.execute(
        "ALTER TABLE invoices "
        "ADD COLUMN IF NOT EXISTS invoicing_contact_email VARCHAR(320)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS invoicing_contact_email")
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS invoicing_contact_name")
