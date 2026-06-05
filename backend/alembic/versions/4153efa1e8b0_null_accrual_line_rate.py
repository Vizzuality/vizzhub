"""null accrual line rate

Revision ID: 4153efa1e8b0
Revises: 086_accrual_period_fx
Create Date: 2026-06-05 21:20:16.003143

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4153efa1e8b0'
down_revision: str | None = '086_accrual_period_fx'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # line.rate is now an override-only column. Every existing value was the
    # auto-derived period/ECB rate (the column was never user-editable), so none
    # are intentional overrides. Null them all → lines default to "follow period".
    # value_eur is deliberately left unchanged: recognized EUR amounts must not move.
    op.execute("UPDATE accrual_lines SET rate = NULL")


def downgrade() -> None:
    # Irreversible: the previous auto-derived rates were not preserved. value_eur
    # is unaffected, so the only loss is the displayed auto-rate, recomputed live
    # from the period anyway.
    pass
