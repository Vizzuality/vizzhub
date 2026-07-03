"""Portfolio Overview import: staging + profile tables."""

from alembic import op

revision = "091_portfolio_overview"
down_revision = "090_client_code_unique"


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE portfolio_match_action AS ENUM ('link', 'create', 'skip');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_overview_staging (
            id uuid PRIMARY KEY,
            import_batch uuid NOT NULL,
            row_index integer NOT NULL,
            name varchar(512) NOT NULL,
            main_partner text,
            on_website boolean,
            client_type_raw text,
            service_raw text,
            impact_area_raw text,
            topics_raw text,
            objective text,
            short_description text,
            stage varchar(128),
            notes text,
            last_update varchar(64),
            web_copy text,
            impact_story text,
            client_contact text,
            is_old_project boolean NOT NULL DEFAULT false,
            matched_program_id uuid REFERENCES programs(id) ON DELETE SET NULL,
            matched_project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
            match_action portfolio_match_action,
            decided_by uuid REFERENCES users(id) ON DELETE SET NULL,
            decided_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_portfolio_staging_batch "
        "ON portfolio_overview_staging (import_batch)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_profile (
            id uuid PRIMARY KEY,
            program_id uuid NOT NULL UNIQUE REFERENCES programs(id) ON DELETE CASCADE,
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


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_profile")
    op.execute("DROP TABLE IF EXISTS portfolio_overview_staging")
    op.execute("DROP TYPE IF EXISTS portfolio_match_action")
