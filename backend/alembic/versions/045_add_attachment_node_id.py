"""Add node_id to registry_attachments for admin traceability."""

revision = "045_attach_node_id"
down_revision = "044_meta_guidance"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade() -> None:
    op.add_column(
        "registry_attachments",
        sa.Column("node_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_registry_attachments_node_id",
        "registry_attachments",
        "iso_doc_nodes",
        ["node_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("""
        UPDATE registry_attachments ra
        SET node_id = rr.node_id
        FROM registry_rows rr
        WHERE ra.row_id = rr.id AND ra.node_id IS NULL
    """)


def downgrade() -> None:
    op.drop_constraint("fk_registry_attachments_node_id", "registry_attachments", type_="foreignkey")
    op.drop_column("registry_attachments", "node_id")
