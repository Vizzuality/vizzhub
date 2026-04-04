"""Add guidance field to iso_doc_metadata."""

revision = "044_meta_guidance"
down_revision = "043_meta_date"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("iso_doc_metadata", sa.Column("guidance", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("iso_doc_metadata", "guidance")
