"""Portfolio import draft: staging new_program_name + applied_at."""

from alembic import op

revision = "094_portfolio_import_draft"
down_revision = "093_portfolio_profile_dual"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE portfolio_overview_staging "
        "ADD COLUMN IF NOT EXISTS new_program_name text"
    )
    op.execute(
        "ALTER TABLE portfolio_overview_staging "
        "ADD COLUMN IF NOT EXISTS applied_at timestamptz"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE portfolio_overview_staging DROP COLUMN IF EXISTS applied_at")
    op.execute("ALTER TABLE portfolio_overview_staging DROP COLUMN IF EXISTS new_program_name")
