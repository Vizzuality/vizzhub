"""Add project_manager_id to projects.

Revision ID: 029
Revises: 028
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "029_add_project_manager"
down_revision: str = "028_add_slack_fields_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "project_manager_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_projects_project_manager_id",
        "projects",
        ["project_manager_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_projects_project_manager_id", table_name="projects")
    op.drop_column("projects", "project_manager_id")
