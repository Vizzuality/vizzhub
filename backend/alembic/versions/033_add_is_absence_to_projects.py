"""Add is_absence to projects."""

from alembic import op
import sqlalchemy as sa

revision = "033_add_is_absence"
down_revision = "032_add_mood_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_absence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_projects_not_billable_and_absence",
        "projects",
        "NOT (is_billable AND is_absence)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_not_billable_and_absence", "projects")
    op.drop_column("projects", "is_absence")
