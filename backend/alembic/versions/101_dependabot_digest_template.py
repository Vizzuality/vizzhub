"""Dependabot alerts become one summary per project with the list in its thread.

The "initial" template now renders the summary; reminders no longer post their
own message, so the "reminder" template is deactivated.

Revision ID: 101_dependabot_digest_template
Revises: 100_program_is_internal
"""

import sqlalchemy as sa

from alembic import op

revision = "101_dependabot_digest_template"
down_revision = "100_program_is_internal"

SUMMARY_TEMPLATE = (
    ":rotating_light: *{project_name}* has {open_count} open high/critical "
    "vulnerabilities ({critical_count} critical, {high_count} high, {new_count} new)\n"
    "*Please, fix them ASAP.* <{alerts_url}|View in GitHub> · full list in the thread"
)

OLD_INITIAL_TEMPLATE = (
    ":red_circle: New {vuln_severity} vulnerability in *{project_name}*\n"
    "Package: {vuln_package}\n"
    "CVE: {vuln_cve}\n"
    "Module: {manifest_path}\n"
    "<{vuln_url}|View in GitHub>"
)

DEPENDABOT_DEFINITION = (
    "alert_definition_id IN "
    "(SELECT id FROM alert_definitions WHERE name = 'dependabot_high_critical')"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE message_templates SET message_template = :tpl "
            f"WHERE template_type = 'initial' AND {DEPENDABOT_DEFINITION}"
        ),
        {"tpl": SUMMARY_TEMPLATE},
    )
    conn.execute(
        sa.text(
            "UPDATE message_templates SET is_active = false "
            f"WHERE template_type = 'reminder' AND {DEPENDABOT_DEFINITION}"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE message_templates SET message_template = :tpl "
            f"WHERE template_type = 'initial' AND {DEPENDABOT_DEFINITION}"
        ),
        {"tpl": OLD_INITIAL_TEMPLATE},
    )
    conn.execute(
        sa.text(
            "UPDATE message_templates SET is_active = true "
            f"WHERE template_type = 'reminder' AND {DEPENDABOT_DEFINITION}"
        )
    )
