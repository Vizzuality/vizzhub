"""Initial schema with projects and metrics tables

Revision ID: 000_initial_schema
Revises:
Create Date: 2026-01-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "000_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jira_project_key", sa.String(50), nullable=True),
        sa.Column("github_repo", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_projects_updated_at
        BEFORE UPDATE ON projects
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create metrics table
    op.create_table(
        "metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("evm_data", sa.JSON(), nullable=True),
        sa.Column("milestones", sa.JSON(), nullable=True),
        sa.Column("jira_defects", sa.JSON(), nullable=True),
        sa.Column("flow_metrics", sa.JSON(), nullable=True),
        sa.Column("github_metrics", sa.JSON(), nullable=True),
        sa.Column("test_maturity", sa.JSON(), nullable=True),
        sa.Column("architecture", sa.JSON(), nullable=True),
        sa.Column("pm_satisfaction", sa.JSON(), nullable=True),
        sa.Column("client_survey", sa.JSON(), nullable=True),
        sa.Column("strategic_impact", sa.String(50), nullable=True),
        sa.Column("governance_exceptions", sa.Integer(), nullable=True),
        sa.Column("sev1_incident", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create index on project_id for faster queries
    op.create_index("ix_metrics_project_id", "metrics", ["project_id"])

    # Create indicators table
    op.create_table(
        "indicators",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("metrics_id", UUID(as_uuid=True), sa.ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spi", sa.Float(), nullable=True),
        sa.Column("on_time_milestones", sa.Float(), nullable=True),
        sa.Column("cpi", sa.Float(), nullable=True),
        sa.Column("budget_variance", sa.Float(), nullable=True),
        sa.Column("defect_density", sa.Float(), nullable=True),
        sa.Column("escaped_rate", sa.Float(), nullable=True),
        sa.Column("mttr_hours", sa.Float(), nullable=True),
        sa.Column("governance_compliance", sa.Float(), nullable=True),
        sa.Column("lead_time_days", sa.Float(), nullable=True),
        sa.Column("flow_efficiency", sa.Float(), nullable=True),
        sa.Column("commitment_reliability", sa.Float(), nullable=True),
        sa.Column("pr_review_ratio", sa.Float(), nullable=True),
        sa.Column("prs_without_review", sa.Integer(), nullable=True),
        sa.Column("high_vulns", sa.Integer(), nullable=True),
        sa.Column("test_maturity", sa.Float(), nullable=True),
        sa.Column("arch_checklist", sa.Float(), nullable=True),
        sa.Column("story_review_ratio", sa.Float(), nullable=True),
        sa.Column("okr_impact", sa.Float(), nullable=True),
        sa.Column("pm_satisfaction", sa.Float(), nullable=True),
        sa.Column("client_satisfaction", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_indicators_metrics_id", "indicators", ["metrics_id"])
    op.create_index("ix_indicators_project_id", "indicators", ["project_id"])

    # Create scores table
    op.create_table(
        "scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("indicators_id", UUID(as_uuid=True), sa.ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("p_time", sa.Integer(), nullable=False),
        sa.Column("p_cost", sa.Integer(), nullable=False),
        sa.Column("p_quality", sa.Integer(), nullable=False),
        sa.Column("p_value", sa.Integer(), nullable=False),
        sa.Column("p_satisfaction", sa.Integer(), nullable=False),
        sa.Column("p_flow", sa.Integer(), nullable=False),
        sa.Column("p_engineering", sa.Integer(), nullable=False),
        sa.Column("p_risk", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_scores_indicators_id", "scores", ["indicators_id"])
    op.create_index("ix_scores_project_id", "scores", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_scores_project_id", table_name="scores")
    op.drop_index("ix_scores_indicators_id", table_name="scores")
    op.drop_table("scores")

    op.drop_index("ix_indicators_project_id", table_name="indicators")
    op.drop_index("ix_indicators_metrics_id", table_name="indicators")
    op.drop_table("indicators")

    op.drop_index("ix_metrics_project_id", table_name="metrics")
    op.drop_table("metrics")

    op.execute("DROP TRIGGER IF EXISTS update_projects_updated_at ON projects")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    op.drop_table("projects")
