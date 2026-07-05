"""Portfolio profile dual-anchor: project_id XOR program_id."""

from alembic import op

revision = "093_portfolio_profile_dual"
down_revision = "092_portfolio_project_first"


def upgrade() -> None:
    op.execute("ALTER TABLE portfolio_profile ALTER COLUMN project_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE portfolio_profile "
        "ADD COLUMN IF NOT EXISTS program_id uuid REFERENCES programs(id) ON DELETE CASCADE"
    )
    # drop the old table-wide unique on project_id (created as a column UNIQUE in 092)
    op.execute(
        "ALTER TABLE portfolio_profile DROP CONSTRAINT IF EXISTS portfolio_profile_project_id_key"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_profile_project "
        "ON portfolio_profile (project_id) WHERE project_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_profile_program "
        "ON portfolio_profile (program_id) WHERE program_id IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE portfolio_profile ADD CONSTRAINT ck_portfolio_profile_one_anchor "
        "CHECK (num_nonnulls(project_id, program_id) = 1)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE portfolio_profile DROP CONSTRAINT IF EXISTS ck_portfolio_profile_one_anchor"
    )
    op.execute("DROP INDEX IF EXISTS uq_portfolio_profile_program")
    op.execute("DROP INDEX IF EXISTS uq_portfolio_profile_project")
    op.execute("ALTER TABLE portfolio_profile DROP COLUMN IF EXISTS program_id")
    op.execute("DELETE FROM portfolio_profile WHERE project_id IS NULL")
    op.execute("ALTER TABLE portfolio_profile ALTER COLUMN project_id SET NOT NULL")
    op.execute(
        "ALTER TABLE portfolio_profile ADD CONSTRAINT portfolio_profile_project_id_key "
        "UNIQUE (project_id)"
    )
