"""Create iso_doc_nodes, iso_doc_versions, iso_doc_metadata tables.

Revision ID: 039_iso_docs
Revises: 038_pb_publish_log
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

revision = "039_iso_docs"
down_revision = "038_pb_publish_log"


def upgrade() -> None:
    iso_doc_node_type = sa.Enum(
        "page", "group", name="iso_doc_node_type", create_type=False,
    )
    iso_doc_category = sa.Enum(
        "manual", "policy", "procedure", "plan", "record", "report",
        name="iso_doc_category", create_type=False,
    )
    iso_doc_status = sa.Enum(
        "draft", "approved", "under_review", name="iso_doc_status",
        create_type=False,
    )

    bind = op.get_bind()
    for enum in (iso_doc_node_type, iso_doc_category, iso_doc_status):
        enum.create(bind, checkfirst=True)

    iso_doc_node_type = sa.Enum(
        "page", "group", name="iso_doc_node_type", create_type=False,
    )
    iso_doc_category = sa.Enum(
        "manual", "policy", "procedure", "plan", "record", "report",
        name="iso_doc_category", create_type=False,
    )
    iso_doc_status = sa.Enum(
        "draft", "approved", "under_review", name="iso_doc_status",
        create_type=False,
    )

    op.create_table(
        "iso_doc_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("type", iso_doc_node_type, nullable=False),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
        sa.UniqueConstraint("parent_id", "slug", name="uq_iso_doc_nodes_parent_slug"),
    )

    op.create_table(
        "iso_doc_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "node_id", "version", name="uq_iso_doc_versions_node_version"
        ),
    )

    op.create_table(
        "iso_doc_metadata",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("standard", ARRAY(sa.String), nullable=True),
        sa.Column("clauses", ARRAY(sa.String), nullable=True),
        sa.Column("category", iso_doc_category, nullable=True),
        sa.Column("doc_version", sa.String(20), nullable=True),
        sa.Column("status", iso_doc_status, nullable=True),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("changelog", JSONB, nullable=True),
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
        sa.UniqueConstraint("node_id", name="uq_iso_doc_metadata_node"),
    )


def downgrade() -> None:
    op.drop_table("iso_doc_metadata")
    op.drop_table("iso_doc_versions")
    op.drop_table("iso_doc_nodes")

    sa.Enum(name="iso_doc_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="iso_doc_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="iso_doc_node_type").drop(op.get_bind(), checkfirst=True)
