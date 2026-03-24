"""Mark Vacation / Absence project with is_absence flag."""

from alembic import op

revision = "033b_mark_absence_proj"
down_revision = "033_add_is_absence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE projects SET is_absence = true WHERE name = 'Vacation / Absence'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE projects SET is_absence = false WHERE name = 'Vacation / Absence'"
    )
