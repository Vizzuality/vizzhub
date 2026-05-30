"""Add fx_rates JSONB to accrual_periods.

Each accounting period stores the FX rate the CEO actually used that period, per
currency — ``{"USD": "1.08", "GBP": "0.85"}`` (units of foreign currency per 1
EUR, same convention as ECB / the Excel header). This is the audit trail of "what
rate produced these figures" and the derivation input for converting
``original_budget`` to EUR going forward. Cells stay in EUR; this does not change
any figure — it records the rate alongside the period.

Empty ``{}`` default: periods with no deduced rate (no foreign-currency lines in
that year) simply carry no rate.

Revision ID: 086_accrual_period_fx
Revises: 085_currency_iso_codes
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "086_accrual_period_fx"
down_revision: str | None = "085_currency_iso_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE accrual_periods ADD COLUMN fx_rates JSONB NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE accrual_periods DROP COLUMN fx_rates")
