"""Drop derived accrual lines of non-billable projects.

Project provisioning used to create a team_budget line for any project with a
budget, billable or not. Non-billable work recognises no revenue, so those lines
inflate the accrual totals. Only auto-derived lines with no manual or frozen
cell, linked solely to non-billable projects, are removed; cells and project
links cascade. Downgrade is a no-op: re-saving a project as billable recreates
its line.

Revision ID: 102_drop_non_billable_lines
Revises: 101_dependabot_digest_template
"""

from alembic import op

revision = "102_drop_non_billable_lines"
down_revision = "101_dependabot_digest_template"


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM accrual_lines l
        WHERE l.source = 'team_budget'
          AND EXISTS (
              SELECT 1 FROM accrual_line_projects lp
              JOIN projects p ON p.id = lp.project_id
              WHERE lp.line_id = l.id AND NOT p.is_billable
          )
          AND NOT EXISTS (
              SELECT 1 FROM accrual_line_projects lp
              JOIN projects p ON p.id = lp.project_id
              WHERE lp.line_id = l.id AND p.is_billable
          )
          AND NOT EXISTS (
              SELECT 1 FROM accrual_cells c
              WHERE c.line_id = l.id AND (c.is_manual_override OR c.is_frozen)
          )
        """
    )


def downgrade() -> None:
    pass
