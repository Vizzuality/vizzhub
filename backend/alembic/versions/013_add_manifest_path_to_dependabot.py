"""Add manifest_path to dependabot_alerts_tracked

Revision ID: 013_add_manifest_path_to_dependabot
Revises: 012_add_users_table
Create Date: 2026-02-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_add_manifest_path"
down_revision: str | None = "012_add_users_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEMPLATES = {
    "initial": (
        ":red_circle: New {vuln_severity} vulnerability in *{project_name}*\n"
        "Package: {vuln_package}\n"
        "CVE: {vuln_cve}\n"
        "Module: {manifest_path}\n"
        "<{vuln_url}|View in GitHub>"
    ),
    "reminder": (
        ":alarm_clock: Reminder: *{project_name}* has unresolved "
        "{vuln_severity} vulnerability\n"
        "Package: {vuln_package} (open for {vuln_age_days} days)\n"
        "Module: {manifest_path}\n"
        "<{vuln_url}|View in GitHub>"
    ),
}

OLD_TEMPLATES = {
    "initial": (
        ":red_circle: New {vuln_severity} vulnerability in *{project_name}*\n"
        "Package: {vuln_package}\n"
        "CVE: {vuln_cve}\n"
        "<{vuln_url}|View in GitHub>"
    ),
    "reminder": (
        ":alarm_clock: Reminder: *{project_name}* has unresolved "
        "{vuln_severity} vulnerability\n"
        "Package: {vuln_package} (open for {vuln_age_days} days)\n"
        "<{vuln_url}|View in GitHub>"
    ),
}


def upgrade() -> None:
    op.add_column(
        "dependabot_alerts_tracked",
        sa.Column("manifest_path", sa.String(500), nullable=True),
    )

    conn = op.get_bind()
    for ttype, template in TEMPLATES.items():
        conn.execute(
            sa.text(
                "UPDATE message_templates SET message_template = :tpl "
                "WHERE template_type = :ttype "
                "AND alert_definition_id IN ("
                "  SELECT id FROM alert_definitions "
                "  WHERE name = 'dependabot_high_critical'"
                ")"
            ),
            {"tpl": template, "ttype": ttype},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for ttype, template in OLD_TEMPLATES.items():
        conn.execute(
            sa.text(
                "UPDATE message_templates SET message_template = :tpl "
                "WHERE template_type = :ttype "
                "AND alert_definition_id IN ("
                "  SELECT id FROM alert_definitions "
                "  WHERE name = 'dependabot_high_critical'"
                ")"
            ),
            {"tpl": template, "ttype": ttype},
        )

    op.drop_column("dependabot_alerts_tracked", "manifest_path")
