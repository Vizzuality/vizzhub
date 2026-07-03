"""Portfolio Overview project-first: re-key profile to project, swap staging decision cols."""

from alembic import op

revision = "092_portfolio_project_first"
down_revision = "091_portfolio_overview"


def upgrade() -> None:
    # profile is empty everywhere → drop + recreate keyed by project_id
    op.execute("DROP TABLE IF EXISTS portfolio_profile")
    op.execute(
        """
        CREATE TABLE portfolio_profile (
            id uuid PRIMARY KEY,
            project_id uuid NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            objective text,
            short_description text,
            web_copy text,
            impact_story text,
            stage varchar(128),
            main_partner text,
            on_website boolean NOT NULL DEFAULT false,
            source_batch uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # staging: swap match_action -> program_action
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE portfolio_program_action AS ENUM ('inherit', 'link', 'create', 'none');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )
    op.execute("ALTER TABLE portfolio_overview_staging DROP COLUMN IF EXISTS match_action")
    op.execute(
        "ALTER TABLE portfolio_overview_staging "
        "ADD COLUMN IF NOT EXISTS program_action portfolio_program_action"
    )
    op.execute("DROP TYPE IF EXISTS portfolio_match_action")


def downgrade() -> None:
    op.execute("ALTER TABLE portfolio_overview_staging DROP COLUMN IF EXISTS program_action")
    op.execute("DROP TYPE IF EXISTS portfolio_program_action")
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE portfolio_match_action AS ENUM ('link', 'create', 'skip');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )
    op.execute(
        "ALTER TABLE portfolio_overview_staging "
        "ADD COLUMN IF NOT EXISTS match_action portfolio_match_action"
    )
    op.execute("DROP TABLE IF EXISTS portfolio_profile")
    op.execute(
        """
        CREATE TABLE portfolio_profile (
            id uuid PRIMARY KEY,
            program_id uuid NOT NULL UNIQUE REFERENCES programs(id) ON DELETE CASCADE,
            objective text, short_description text, web_copy text, impact_story text,
            stage varchar(128), main_partner text,
            on_website boolean NOT NULL DEFAULT false, source_batch uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
