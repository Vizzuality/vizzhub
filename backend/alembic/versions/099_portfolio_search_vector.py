"""Full-text search vector on portfolio_profile narrative fields.

Revision ID: 099_portfolio_search_vector
Revises: 098_profile_website_url
"""

from alembic import op

revision = "099_portfolio_search_vector"
down_revision = "098_profile_website_url"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE portfolio_profile ADD COLUMN IF NOT EXISTS search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(objective,'') || ' ' || "
        "coalesce(short_description,'') || ' ' || coalesce(impact_story,'') || ' ' || "
        "coalesce(web_copy,'') || ' ' || coalesce(main_partner,''))) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_portfolio_profile_search "
        "ON portfolio_profile USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_portfolio_profile_search")
    op.execute("ALTER TABLE portfolio_profile DROP COLUMN IF EXISTS search_vector")
