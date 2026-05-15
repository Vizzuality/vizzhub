"""Add CHECK (base_rate > 0) to reporting_periods.

Audit #25 (2026-05-15): cost calculation does
contract_rate / base_rate; a zero base_rate crashes report-part
creation with a 500. Enforce > 0 at the database level alongside
the Pydantic Field(gt=0) on ReportingPeriodCreate/Update.
"""

from alembic import op

revision = "071_period_base_rate_gt0"
down_revision = "070_global_by_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE reporting_periods
            ADD CONSTRAINT ck_reporting_periods_base_rate_positive
            CHECK (base_rate > 0);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE reporting_periods "
        "DROP CONSTRAINT IF EXISTS ck_reporting_periods_base_rate_positive"
    )
