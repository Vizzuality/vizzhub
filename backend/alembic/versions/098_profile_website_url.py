"""Add website_url to portfolio_profile.

Revision ID: 098_profile_website_url
Revises: 097_portfolio_manager_role
"""

from alembic import op

revision = "098_profile_website_url"
down_revision = "097_portfolio_manager_role"


def upgrade() -> None:
    op.execute("ALTER TABLE portfolio_profile ADD COLUMN IF NOT EXISTS website_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE portfolio_profile DROP COLUMN IF EXISTS website_url")
