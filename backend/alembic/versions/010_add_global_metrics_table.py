"""Add global_metrics table for averaged metrics across all projects

Revision ID: 010_add_global_metrics_table
Revises: 009_add_project_finished_at
Create Date: 2026-02-02

This migration adds the global_metrics table to store monthly averages
of indicators and scores across all projects. Each indicator stores
both its averaged value and the count of projects that contributed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "010_add_global_metrics_table"
down_revision: Union[str, None] = "009_add_project_finished_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "global_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("project_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Averaged Indicators (0-1 scale) + counts
        sa.Column("spi", sa.Float(), nullable=True),
        sa.Column("spi_count", sa.Integer(), nullable=True),
        sa.Column("cpi", sa.Float(), nullable=True),
        sa.Column("cpi_count", sa.Integer(), nullable=True),
        sa.Column("on_time_milestones", sa.Float(), nullable=True),
        sa.Column("on_time_milestones_count", sa.Integer(), nullable=True),
        sa.Column("defect_density", sa.Float(), nullable=True),
        sa.Column("defect_density_count", sa.Integer(), nullable=True),
        sa.Column("escaped_rate", sa.Float(), nullable=True),
        sa.Column("escaped_rate_count", sa.Integer(), nullable=True),
        sa.Column("mttr_hours", sa.Float(), nullable=True),
        sa.Column("mttr_hours_count", sa.Integer(), nullable=True),
        sa.Column("governance_compliance", sa.Float(), nullable=True),
        sa.Column("governance_compliance_count", sa.Integer(), nullable=True),
        sa.Column("lead_time_days", sa.Float(), nullable=True),
        sa.Column("lead_time_days_count", sa.Integer(), nullable=True),
        sa.Column("deployment_frequency", sa.Float(), nullable=True),
        sa.Column("deployment_frequency_count", sa.Integer(), nullable=True),
        sa.Column("change_failure_rate", sa.Float(), nullable=True),
        sa.Column("change_failure_rate_count", sa.Integer(), nullable=True),
        sa.Column("commitment_reliability", sa.Float(), nullable=True),
        sa.Column("commitment_reliability_count", sa.Integer(), nullable=True),
        sa.Column("pr_review_ratio", sa.Float(), nullable=True),
        sa.Column("pr_review_ratio_count", sa.Integer(), nullable=True),
        sa.Column("test_maturity", sa.Float(), nullable=True),
        sa.Column("test_maturity_count", sa.Integer(), nullable=True),
        sa.Column("arch_checklist", sa.Float(), nullable=True),
        sa.Column("arch_checklist_count", sa.Integer(), nullable=True),
        sa.Column("high_vulns", sa.Float(), nullable=True),
        sa.Column("high_vulns_count", sa.Integer(), nullable=True),
        sa.Column("okr_impact", sa.Float(), nullable=True),
        sa.Column("okr_impact_count", sa.Integer(), nullable=True),
        sa.Column("pm_satisfaction", sa.Float(), nullable=True),
        sa.Column("pm_satisfaction_count", sa.Integer(), nullable=True),
        sa.Column("client_satisfaction", sa.Float(), nullable=True),
        sa.Column("client_satisfaction_count", sa.Integer(), nullable=True),
        sa.Column("story_review_ratio", sa.Float(), nullable=True),
        sa.Column("story_review_ratio_count", sa.Integer(), nullable=True),
        sa.Column("strategic_impact", sa.Float(), nullable=True),
        sa.Column("strategic_impact_count", sa.Integer(), nullable=True),
        # Averaged Dimension Scores (0-100 scale) + counts
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_count", sa.Integer(), nullable=True),
        sa.Column("p_time", sa.Float(), nullable=True),
        sa.Column("p_time_count", sa.Integer(), nullable=True),
        sa.Column("p_cost", sa.Float(), nullable=True),
        sa.Column("p_cost_count", sa.Integer(), nullable=True),
        sa.Column("p_quality", sa.Float(), nullable=True),
        sa.Column("p_quality_count", sa.Integer(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("p_value_count", sa.Integer(), nullable=True),
        sa.Column("p_satisfaction", sa.Float(), nullable=True),
        sa.Column("p_satisfaction_count", sa.Integer(), nullable=True),
        sa.Column("p_flow", sa.Float(), nullable=True),
        sa.Column("p_flow_count", sa.Integer(), nullable=True),
        sa.Column("p_engineering", sa.Float(), nullable=True),
        sa.Column("p_engineering_count", sa.Integer(), nullable=True),
        sa.Column("p_risk", sa.Float(), nullable=True),
        sa.Column("p_risk_count", sa.Integer(), nullable=True),
        # Unique constraint on period
        sa.UniqueConstraint("period_year", "period_month", name="uq_global_metrics_period"),
    )

    # Indexes for common queries
    op.create_index("ix_global_metrics_period", "global_metrics", ["period_year", "period_month"])


def downgrade() -> None:
    op.drop_index("ix_global_metrics_period", table_name="global_metrics")
    op.drop_table("global_metrics")
