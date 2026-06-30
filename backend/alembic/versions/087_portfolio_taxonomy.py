"""Portfolio taxonomy tables: taxonomies, taxonomy_terms, entity_terms."""

from alembic import op

revision = "087_portfolio_taxonomy"
down_revision = "4153efa1e8b0"


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE taxonomy_cardinality AS ENUM ('single', 'multi');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taxonomies (
            id uuid PRIMARY KEY,
            slug varchar(64) NOT NULL UNIQUE,
            name varchar(128) NOT NULL,
            description text,
            cardinality taxonomy_cardinality NOT NULL DEFAULT 'multi',
            allows_primary boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            sort_order integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS taxonomy_terms (
            id uuid PRIMARY KEY,
            taxonomy_id uuid NOT NULL REFERENCES taxonomies(id) ON DELETE CASCADE,
            slug varchar(64) NOT NULL,
            name varchar(128) NOT NULL,
            description text,
            sort_order integer NOT NULL DEFAULT 0,
            is_active boolean NOT NULL DEFAULT true,
            CONSTRAINT uq_taxonomy_terms_tax_slug UNIQUE (taxonomy_id, slug)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_terms (
            id uuid PRIMARY KEY,
            term_id uuid NOT NULL REFERENCES taxonomy_terms(id) ON DELETE CASCADE,
            taxonomy_id uuid NOT NULL REFERENCES taxonomies(id) ON DELETE CASCADE,
            program_id uuid REFERENCES programs(id) ON DELETE CASCADE,
            project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
            is_primary boolean NOT NULL DEFAULT false,
            assigned_at timestamptz NOT NULL DEFAULT now(),
            assigned_by uuid REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT ck_entity_terms_one_entity CHECK (num_nonnulls(program_id, project_id) = 1)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_terms_program_primary "
        "ON entity_terms (program_id, taxonomy_id) WHERE is_primary"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_terms_project_primary "
        "ON entity_terms (project_id, taxonomy_id) WHERE is_primary"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_entity_terms_project ON entity_terms (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entity_terms_program ON entity_terms (program_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entity_terms_term ON entity_terms (term_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entity_terms")
    op.execute("DROP TABLE IF EXISTS taxonomy_terms")
    op.execute("DROP TABLE IF EXISTS taxonomies")
    op.execute("DROP TYPE IF EXISTS taxonomy_cardinality")
