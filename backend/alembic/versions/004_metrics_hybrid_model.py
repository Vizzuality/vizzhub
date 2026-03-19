"""Migrate metrics table to hybrid model with normalized columns

Revision ID: 004_metrics_hybrid_model
Revises: 003_add_metric_snapshots
Create Date: 2026-01-28

This migration:
1. Adds normalized columns for EVM, defects, flow, and GitHub metrics
2. Migrates existing JSON data to new columns
3. Drops old JSON columns (evm_data, jira_defects, flow_metrics, github_metrics)
4. Keeps JSON columns for variable structures (milestones, test_maturity, architecture, pm_satisfaction, client_survey)

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004_metrics_hybrid_model"
down_revision: str | None = "003_add_metric_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === Add EVM columns ===
    op.add_column("metrics", sa.Column("budget_total", sa.Numeric(15, 2), nullable=True))
    op.add_column("metrics", sa.Column("cost_to_date", sa.Numeric(15, 2), nullable=True))
    op.add_column("metrics", sa.Column("percent_completed", sa.Numeric(5, 4), nullable=True))
    op.add_column("metrics", sa.Column("percent_planned", sa.Numeric(5, 4), nullable=True))

    # === Add defect metric columns ===
    op.add_column("metrics", sa.Column("bugs_total", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("tasks_completed", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("escaped_defects", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("mttr_hours", sa.Numeric(10, 2), nullable=True))
    op.add_column("metrics", sa.Column("incidents_count", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("post_contract_tasks", sa.Integer(), nullable=True))

    # === Add flow metric columns ===
    op.add_column("metrics", sa.Column("lead_time_days", sa.Numeric(10, 2), nullable=True))
    op.add_column("metrics", sa.Column("lead_time_sample_size", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("commitment_reliability", sa.Numeric(5, 4), nullable=True))
    op.add_column("metrics", sa.Column("committed_issues", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("single_sprint_issues", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("multi_sprint_issues", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("total_stories", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("stories_with_reviewer", sa.Integer(), nullable=True))

    # === Add GitHub metric columns ===
    op.add_column("metrics", sa.Column("prs_without_review", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("total_merged_prs", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("high_severity_vulns", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("high_severity_vulns_total", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("pr_size_median", sa.Numeric(10, 2), nullable=True))
    op.add_column("metrics", sa.Column("review_turnaround_hours", sa.Numeric(10, 2), nullable=True))
    op.add_column("metrics", sa.Column("deployment_frequency", sa.Numeric(10, 6), nullable=True))
    op.add_column("metrics", sa.Column("release_count_90d", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("change_failure_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("metrics", sa.Column("total_releases", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("failed_releases", sa.Integer(), nullable=True))

    # === Migrate existing JSON data to new columns ===
    op.execute("""
        UPDATE metrics SET
            -- EVM data
            budget_total = (evm_data->>'budget_total')::NUMERIC(15,2),
            cost_to_date = (evm_data->>'cost_to_date')::NUMERIC(15,2),
            percent_completed = (evm_data->>'percent_completed')::NUMERIC(5,4),
            percent_planned = (evm_data->>'percent_planned')::NUMERIC(5,4),
            -- Defect metrics
            bugs_total = (jira_defects->>'bugs_total')::INTEGER,
            tasks_completed = (jira_defects->>'tasks_completed')::INTEGER,
            escaped_defects = (jira_defects->>'escaped_defects')::INTEGER,
            mttr_hours = (jira_defects->>'mttr_hours')::NUMERIC(10,2),
            incidents_count = (jira_defects->>'incidents_count')::INTEGER,
            post_contract_tasks = (jira_defects->>'post_contract_tasks')::INTEGER,
            -- Flow metrics
            lead_time_days = (flow_metrics->>'lead_time_days')::NUMERIC(10,2),
            lead_time_sample_size = (flow_metrics->>'lead_time_sample_size')::INTEGER,
            commitment_reliability = (flow_metrics->>'commitment_reliability')::NUMERIC(5,4),
            committed_issues = (flow_metrics->>'committed_issues')::INTEGER,
            single_sprint_issues = (flow_metrics->>'single_sprint_issues')::INTEGER,
            multi_sprint_issues = (flow_metrics->>'multi_sprint_issues')::INTEGER,
            total_stories = (flow_metrics->>'total_stories')::INTEGER,
            stories_with_reviewer = (flow_metrics->>'stories_with_reviewer')::INTEGER,
            -- GitHub metrics
            prs_without_review = (github_metrics->>'prs_without_review')::INTEGER,
            total_merged_prs = (github_metrics->>'total_merged_prs')::INTEGER,
            high_severity_vulns = (github_metrics->>'high_severity_vulns')::INTEGER,
            high_severity_vulns_total = (github_metrics->>'high_severity_vulns_total')::INTEGER,
            pr_size_median = (github_metrics->>'pr_size_median')::NUMERIC(10,2),
            review_turnaround_hours = (github_metrics->>'review_turnaround_hours')::NUMERIC(10,2),
            deployment_frequency = (github_metrics->>'deployment_frequency')::NUMERIC(10,6),
            release_count_90d = (github_metrics->>'release_count_90d')::INTEGER,
            change_failure_rate = (github_metrics->>'change_failure_rate')::NUMERIC(5,4),
            total_releases = (github_metrics->>'total_releases')::INTEGER,
            failed_releases = (github_metrics->>'failed_releases')::INTEGER
        WHERE evm_data IS NOT NULL
           OR jira_defects IS NOT NULL
           OR flow_metrics IS NOT NULL
           OR github_metrics IS NOT NULL
    """)

    # === Drop old JSON columns ===
    op.drop_column("metrics", "evm_data")
    op.drop_column("metrics", "jira_defects")
    op.drop_column("metrics", "flow_metrics")
    op.drop_column("metrics", "github_metrics")

    # === Add indexes for common queries ===
    op.create_index("ix_metrics_period_end", "metrics", ["period_end"])


def downgrade() -> None:
    # Remove index
    op.drop_index("ix_metrics_period_end", table_name="metrics")

    # Re-add JSON columns
    op.add_column("metrics", sa.Column("evm_data", sa.JSON(), nullable=True))
    op.add_column("metrics", sa.Column("jira_defects", sa.JSON(), nullable=True))
    op.add_column("metrics", sa.Column("flow_metrics", sa.JSON(), nullable=True))
    op.add_column("metrics", sa.Column("github_metrics", sa.JSON(), nullable=True))

    # Migrate data back to JSON
    op.execute("""
        UPDATE metrics SET
            evm_data = jsonb_build_object(
                'budget_total', budget_total,
                'cost_to_date', cost_to_date,
                'percent_completed', percent_completed,
                'percent_planned', percent_planned
            ),
            jira_defects = jsonb_build_object(
                'bugs_total', bugs_total,
                'tasks_completed', tasks_completed,
                'escaped_defects', escaped_defects,
                'mttr_hours', mttr_hours,
                'incidents_count', incidents_count,
                'post_contract_tasks', post_contract_tasks
            ),
            flow_metrics = jsonb_build_object(
                'lead_time_days', lead_time_days,
                'lead_time_sample_size', lead_time_sample_size,
                'commitment_reliability', commitment_reliability,
                'committed_issues', committed_issues,
                'single_sprint_issues', single_sprint_issues,
                'multi_sprint_issues', multi_sprint_issues,
                'total_stories', total_stories,
                'stories_with_reviewer', stories_with_reviewer
            ),
            github_metrics = jsonb_build_object(
                'prs_without_review', prs_without_review,
                'total_merged_prs', total_merged_prs,
                'high_severity_vulns', high_severity_vulns,
                'high_severity_vulns_total', high_severity_vulns_total,
                'pr_size_median', pr_size_median,
                'review_turnaround_hours', review_turnaround_hours,
                'deployment_frequency', deployment_frequency,
                'release_count_90d', release_count_90d,
                'change_failure_rate', change_failure_rate,
                'total_releases', total_releases,
                'failed_releases', failed_releases
            )
        WHERE budget_total IS NOT NULL
           OR bugs_total IS NOT NULL
           OR lead_time_days IS NOT NULL
           OR prs_without_review IS NOT NULL
    """)

    # Drop normalized columns
    # EVM
    op.drop_column("metrics", "budget_total")
    op.drop_column("metrics", "cost_to_date")
    op.drop_column("metrics", "percent_completed")
    op.drop_column("metrics", "percent_planned")
    # Defects
    op.drop_column("metrics", "bugs_total")
    op.drop_column("metrics", "tasks_completed")
    op.drop_column("metrics", "escaped_defects")
    op.drop_column("metrics", "mttr_hours")
    op.drop_column("metrics", "incidents_count")
    op.drop_column("metrics", "post_contract_tasks")
    # Flow
    op.drop_column("metrics", "lead_time_days")
    op.drop_column("metrics", "lead_time_sample_size")
    op.drop_column("metrics", "commitment_reliability")
    op.drop_column("metrics", "committed_issues")
    op.drop_column("metrics", "single_sprint_issues")
    op.drop_column("metrics", "multi_sprint_issues")
    op.drop_column("metrics", "total_stories")
    op.drop_column("metrics", "stories_with_reviewer")
    # GitHub
    op.drop_column("metrics", "prs_without_review")
    op.drop_column("metrics", "total_merged_prs")
    op.drop_column("metrics", "high_severity_vulns")
    op.drop_column("metrics", "high_severity_vulns_total")
    op.drop_column("metrics", "pr_size_median")
    op.drop_column("metrics", "review_turnaround_hours")
    op.drop_column("metrics", "deployment_frequency")
    op.drop_column("metrics", "release_count_90d")
    op.drop_column("metrics", "change_failure_rate")
    op.drop_column("metrics", "total_releases")
    op.drop_column("metrics", "failed_releases")
