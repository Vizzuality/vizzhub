"""Add approval workflow fields to invoice_postponements.

A postpone is no longer instantaneous — it is now a request that must be
approved by an admin. We model the decision lifecycle on the postponement
row itself:

- approval_status: pending → approved | rejected | cancelled
- decided_by / decided_at: who closed the request (approver, rejector,
  or the requester themselves on cancel)
- decision_note: optional context, required on reject

Existing postponements were instantaneously effective. The backfill marks
them all ``approved`` with ``decided_at = created_at`` and
``decided_by = created_by`` so the effective-status logic behaves
exactly as before for historical data.
"""

from alembic import op

revision = "075_postponement_approval"
down_revision = "074_invoice_contact_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20)"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD COLUMN IF NOT EXISTS decided_by UUID"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD CONSTRAINT fk_invoice_postponements_decided_by "
        "FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD COLUMN IF NOT EXISTS decision_note TEXT"
    )
    # Backfill: every pre-existing row was effective immediately, so treat
    # them as approved by their original creator at creation time.
    op.execute(
        "UPDATE invoice_postponements "
        "SET approval_status = 'approved', "
        "    decided_by = created_by, "
        "    decided_at = created_at "
        "WHERE approval_status IS NULL"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ALTER COLUMN approval_status SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ALTER COLUMN approval_status SET DEFAULT 'pending'"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "ADD CONSTRAINT ck_invoice_postponements_approval_status "
        "CHECK (approval_status IN ('pending', 'approved', 'rejected', 'cancelled'))"
    )
    # Only one pending request at a time per invoice.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_postponements_one_pending "
        "ON invoice_postponements (invoice_id) "
        "WHERE approval_status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_invoice_postponements_one_pending")
    op.execute(
        "ALTER TABLE invoice_postponements "
        "DROP CONSTRAINT IF EXISTS ck_invoice_postponements_approval_status"
    )
    op.execute(
        "ALTER TABLE invoice_postponements "
        "DROP CONSTRAINT IF EXISTS fk_invoice_postponements_decided_by"
    )
    op.execute("ALTER TABLE invoice_postponements DROP COLUMN IF EXISTS decision_note")
    op.execute("ALTER TABLE invoice_postponements DROP COLUMN IF EXISTS decided_at")
    op.execute("ALTER TABLE invoice_postponements DROP COLUMN IF EXISTS decided_by")
    op.execute("ALTER TABLE invoice_postponements DROP COLUMN IF EXISTS approval_status")
