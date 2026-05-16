"""Rename config target_budget_variance → target_cost_variance.

Audit #18 (2026-05-16): the cost dimension previously used a clamped
overrun-only `budget_variance` indicator that lost the under-budget
signal and ignored progress entirely. Replaced with the EVM-standard
signed Cost Variance percentage (CV / BAC). The seeded
`config_parameters` row that fed this normalizer is renamed in place;
the numeric value carries over since it represents the same magnitude
of tolerance, now interpreted as "tolerance for under-delivery relative
to spend" rather than "tolerance for overrun".

Idempotent: the UPDATE no-ops if the row has already been renamed.

Scorecard history must be recalculated after deploy (CTO Option B).
"""

from alembic import op


revision = "072_cv_pct_replaces_bv"
down_revision = "071_period_base_rate_gt0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE config_parameters
        SET name = 'target_cost_variance'
        WHERE name = 'target_budget_variance'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE config_parameters
        SET name = 'target_budget_variance'
        WHERE name = 'target_cost_variance'
        """
    )
