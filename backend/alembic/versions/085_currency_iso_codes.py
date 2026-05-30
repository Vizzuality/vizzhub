"""Widen projects.currency to allow ISO 4217 codes alongside legacy labels.

``projects.currency`` is the source of truth for a project's billing currency
(used for invoices + ``original_budget`` provenance; the platform otherwise
operates in EUR). The legacy ``ck_projects_currency_valid`` constraint locked it
to ``'euro'`` / ``'dollar'``, which can't express GBP/CAD — so projects funded in
pounds (UK clients) or other currencies were mislabelled.

This relaxes the constraint to accept ISO codes (``EUR``/``USD``/``GBP``/``CAD``)
while keeping the legacy labels valid: the long tail of projects stays on
``dollar``/``euro`` (normalised at read via ``currency_to_code``); only projects
with evidence get the precise ISO code. No data is converted here — the one-time
reclassification runs as a separate idempotent script.

Reversible: downgrade maps any ISO value back to a legacy label before
re-narrowing the constraint.

Revision ID: 085_currency_iso_codes
Revises: 084_accrual_cells_cleanup
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "085_currency_iso_codes"
down_revision: str | None = "084_accrual_cells_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WIDE = "currency IN ('euro', 'dollar', 'EUR', 'USD', 'GBP', 'CAD')"
_NARROW = "currency IN ('euro', 'dollar')"


def upgrade() -> None:
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_projects_currency_valid")
    op.execute(f"ALTER TABLE projects ADD CONSTRAINT ck_projects_currency_valid CHECK ({_WIDE})")


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_projects_currency_valid")
    op.execute("UPDATE projects SET currency = 'dollar' WHERE currency IN ('USD', 'GBP', 'CAD')")
    op.execute("UPDATE projects SET currency = 'euro' WHERE currency = 'EUR'")
    op.execute(f"ALTER TABLE projects ADD CONSTRAINT ck_projects_currency_valid CHECK ({_NARROW})")
