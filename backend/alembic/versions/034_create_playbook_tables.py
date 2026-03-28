"""Create playbook tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "034_create_playbook"
down_revision = "033b_mark_absence_proj"
branch_labels = None
depends_on = None


def upgrade() -> None:
    users_id = "users.id"
    set_null = "SET NULL"
    op.create_table(
        "playbook_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.Enum("page", "group", name="playbook_node_type"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "is_public", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey(users_id, ondelete=set_null),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey(users_id, ondelete=set_null),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("parent_id", "slug", name="uq_playbook_nodes_parent_slug"),
    )

    op.create_table(
        "playbook_page_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey(users_id, ondelete=set_null),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "node_id", "version", name="uq_playbook_versions_node_version"
        ),
    )

    op.create_index(
        "ix_playbook_nodes_parent_position",
        "playbook_nodes",
        ["parent_id", "position"],
    )
    op.create_index(
        "ix_playbook_versions_node_id",
        "playbook_page_versions",
        ["node_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_playbook_versions_node_id")
    op.drop_index("ix_playbook_nodes_parent_position")
    op.drop_table("playbook_page_versions")
    op.drop_table("playbook_nodes")
    op.execute("DROP TYPE IF EXISTS playbook_node_type")
