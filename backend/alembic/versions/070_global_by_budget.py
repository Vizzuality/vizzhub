"""Add budget-weighted score columns to global_metrics.

Audit #17 (2026-05-15): the portfolio aggregate also exposes a
budget-weighted version of each dimension and the overall score.
Projects without a budget are excluded from the budget-weighted
aggregate (tracked in budget_weighted_project_count).
"""

from alembic import op

revision = "070_global_by_budget"
down_revision = "069_jobs_status_created_idx"
branch_labels = None
depends_on = None

NEW_COLUMNS = [
    "budget_weighted_project_count INTEGER",
    "score_by_budget DOUBLE PRECISION",
    "p_time_by_budget DOUBLE PRECISION",
    "p_cost_by_budget DOUBLE PRECISION",
    "p_quality_by_budget DOUBLE PRECISION",
    "p_value_by_budget DOUBLE PRECISION",
    "p_satisfaction_by_budget DOUBLE PRECISION",
    "p_flow_by_budget DOUBLE PRECISION",
    "p_engineering_by_budget DOUBLE PRECISION",
    "p_risk_by_budget DOUBLE PRECISION",
]


def upgrade() -> None:
    for col_def in NEW_COLUMNS:
        op.execute(f"ALTER TABLE global_metrics ADD COLUMN IF NOT EXISTS {col_def}")


def downgrade() -> None:
    for col_def in NEW_COLUMNS:
        col_name = col_def.split(" ", 1)[0]
        op.execute(f"ALTER TABLE global_metrics DROP COLUMN IF EXISTS {col_name}")
