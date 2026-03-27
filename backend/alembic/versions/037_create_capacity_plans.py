"""Create capacity_plans table.

Revision ID: 037_capacity_plans
Revises: 036_invoice_postponed_alert
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "037_capacity_plans"
down_revision = "036_invoice_postponed_alert"


def upgrade() -> None:
    op.create_table(
        "capacity_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("percentage", sa.SmallInteger, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", "week_start", name="uq_capacity_plan_cell"),
        sa.CheckConstraint("percentage >= 1 AND percentage <= 200", name="ck_capacity_plan_pct"),
        sa.CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_capacity_plan_monday"),
    )
    op.create_index("ix_capacity_plans_project_user", "capacity_plans", ["project_id", "user_id"])
    op.create_index("ix_capacity_plans_week", "capacity_plans", ["week_start"])


def downgrade() -> None:
    op.drop_index("ix_capacity_plans_week")
    op.drop_index("ix_capacity_plans_project_user")
    op.drop_table("capacity_plans")
