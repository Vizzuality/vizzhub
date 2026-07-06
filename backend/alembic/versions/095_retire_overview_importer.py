"""Retire the Portfolio Overview importer: drop staging table + program_action enum.

The importer was a throwaway one-off review tool. Its output (portfolio_profile,
programs, entity_terms) is kept; only the staging scratch table and its enum go.
"""

from alembic import op

revision = "095_retire_overview_importer"
down_revision = "094_portfolio_import_draft"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_overview_staging")
    op.execute("DROP TYPE IF EXISTS portfolio_program_action")


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE portfolio_program_action AS ENUM ('inherit', 'link', 'create', 'none');
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
            program_action portfolio_program_action,
            decided_by uuid REFERENCES users(id) ON DELETE SET NULL,
            decided_at timestamptz,
            new_program_name text,
            applied_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_portfolio_staging_batch "
        "ON portfolio_overview_staging (import_batch)"
    )
