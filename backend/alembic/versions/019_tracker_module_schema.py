"""Tracker module schema: reporting_periods, budget_lines, invoices, etc.

Revision ID: 019_tracker_module
Revises: 018_tracker_core
Create Date: 2026-03-14

Creates all tracker-owned tables: tracker_project_settings, reporting_periods,
budget_lines, invoices, non_staff_costs, reports, report_parts, progress_reports.
Includes all CHECK constraints, UNIQUE constraints, composite indexes,
and partial indexes as specified in the data migration design doc.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019_tracker_module"
down_revision: Union[str, None] = "018_tracker_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. tracker_project_settings
    op.create_table(
        "tracker_project_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("contract_rate", sa.Numeric(12, 2), nullable=False,
                  server_default="175.00"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    # 2. reporting_periods
    op.create_table(
        "reporting_periods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("base_rate", sa.Numeric(12, 2), nullable=False,
                  server_default="175.00"),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="unstarted"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('unstarted', 'active', 'finished')",
            name="ck_reporting_periods_status_valid",
        ),
    )
    op.create_index(
        "ix_reporting_periods_unique_active",
        "reporting_periods",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # 3. budget_lines
    op.create_table(
        "budget_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("functional_area_id", UUID(as_uuid=True),
                  sa.ForeignKey("functional_areas.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("days", sa.Integer(), nullable=True),
        sa.Column("adjusted_days", sa.Numeric(8, 2), nullable=True),
        sa.Column("percentage", sa.Numeric(5, 4), nullable=True),
        sa.Column("details", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 1)",
            name="ck_budget_lines_percentage_range",
        ),
        sa.CheckConstraint(
            "days IS NULL OR days >= 0",
            name="ck_budget_lines_days_positive",
        ),
    )
    op.create_index("ix_budget_lines_project_id", "budget_lines", ["project_id"])
    op.create_index("ix_budget_lines_functional_area_id", "budget_lines",
                    ["functional_area_id"])
    op.create_index("ix_budget_lines_project_area", "budget_lines",
                    ["project_id", "functional_area_id"])

    # 4. invoices
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("code", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(20), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("extended_date", sa.Date(), nullable=True),
        sa.Column("invoiced_on", sa.Date(), nullable=True),
        sa.Column("milestone", sa.Text(), nullable=False),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False,
                  server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint("amount >= 0", name="ck_invoices_amount_positive"),
        sa.CheckConstraint(
            "currency IN ('euro', 'dollar')",
            name="ck_invoices_currency_valid",
        ),
        sa.CheckConstraint(
            "extended_date IS NULL OR due_date IS NULL OR extended_date >= due_date",
            name="ck_invoices_extended_after_due",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'pending_to_issue', 'waiting_for_payment', 'paid')",
            name="ck_invoices_status_valid",
        ),
    )
    op.create_index("ix_invoices_project_status", "invoices",
                    ["project_id", "status"])

    # 5. non_staff_costs
    op.create_table(
        "non_staff_costs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("reporting_period_id", UUID(as_uuid=True),
                  sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost_type", sa.String(50), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.CheckConstraint("cost >= 0", name="ck_non_staff_costs_cost_positive"),
        sa.CheckConstraint(
            "cost_type IN ('outsource', 'travel', 'servers', 'others')",
            name="ck_non_staff_costs_type_valid",
        ),
    )
    op.create_index("ix_non_staff_costs_project_id", "non_staff_costs",
                    ["project_id"])
    op.create_index("ix_non_staff_costs_reporting_period_id", "non_staff_costs",
                    ["reporting_period_id"])
    op.create_index("ix_non_staff_costs_project_period", "non_staff_costs",
                    ["project_id", "reporting_period_id"])

    # 6. reports
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("reporting_period_id", UUID(as_uuid=True),
                  sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "reporting_period_id",
                           name="uq_reports_user_period"),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_reports_reporting_period_id", "reports",
                    ["reporting_period_id"])
    op.create_index(
        "ix_reports_period_id_include_user",
        "reports",
        ["reporting_period_id"],
        postgresql_include=["user_id"],
    )
    op.create_index(
        "ix_reports_period_not_estimated",
        "reports",
        ["reporting_period_id"],
        postgresql_where=sa.text("estimated = false"),
    )

    # 7. report_parts
    op.create_table(
        "report_parts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", UUID(as_uuid=True),
                  sa.ForeignKey("reports.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("functional_area_id", UUID(as_uuid=True),
                  sa.ForeignKey("functional_areas.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("percentage", sa.Numeric(5, 4), nullable=True),
        sa.Column("days", sa.Numeric(8, 4), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "report_id", "functional_area_id",
                           name="uq_report_parts_project_report_area"),
        sa.CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 1)",
            name="ck_report_parts_percentage_range",
        ),
        sa.CheckConstraint("cost IS NULL OR cost >= 0",
                          name="ck_report_parts_cost_positive"),
        sa.CheckConstraint("days IS NULL OR days >= 0",
                          name="ck_report_parts_days_positive"),
    )
    op.create_index("ix_report_parts_report_id", "report_parts", ["report_id"])
    op.create_index("ix_report_parts_project_id", "report_parts", ["project_id"])
    op.create_index("ix_report_parts_functional_area_id", "report_parts",
                    ["functional_area_id"])
    op.create_index("ix_report_parts_project_area", "report_parts",
                    ["project_id", "functional_area_id"])

    # 8. progress_reports
    op.create_table(
        "progress_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("reporting_period_id", UUID(as_uuid=True),
                  sa.ForeignKey("reporting_periods.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("percentage", sa.Numeric(5, 4), nullable=False),
        sa.Column("delta", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("reporting_period_id", "project_id",
                           name="uq_progress_reports_period_project"),
        sa.CheckConstraint(
            "percentage >= 0 AND percentage <= 1",
            name="ck_progress_reports_percentage_range",
        ),
        sa.CheckConstraint(
            "delta >= -1 AND delta <= 1",
            name="ck_progress_reports_delta_range",
        ),
    )
    op.create_index("ix_progress_reports_project_id", "progress_reports",
                    ["project_id"])
    op.create_index("ix_progress_reports_reporting_period_id", "progress_reports",
                    ["reporting_period_id"])
    op.create_index("ix_progress_reports_project_period", "progress_reports",
                    ["project_id", "reporting_period_id"])


def downgrade() -> None:
    op.drop_table("progress_reports")
    op.drop_table("report_parts")
    op.drop_table("reports")
    op.drop_table("non_staff_costs")
    op.drop_table("invoices")
    op.drop_table("budget_lines")
    op.drop_table("reporting_periods")
    op.drop_table("tracker_project_settings")
