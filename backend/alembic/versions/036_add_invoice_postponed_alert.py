"""Add invoice_postponed alert definition and template.

Revision ID: 036_invoice_postponed_alert
Revises: 035_add_playbook_editor
"""

from alembic import op

revision = "036_invoice_postponed_alert"
down_revision = "035_add_playbook_editor"


def upgrade() -> None:
    op.execute("""
        INSERT INTO alert_definitions (name, description, category, channel_type, schedule, is_enabled, config_json)
        VALUES (
            'invoice_postponed',
            'Sends a Slack DM when an invoice is postponed.',
            'business',
            'leadership',
            'event',
            true,
            '{"recipient_slack_user_id": ""}'::jsonb
        )
    """)
    op.execute("""
        INSERT INTO message_templates (alert_definition_id, template_type, message_template, is_active)
        VALUES (
            (SELECT id FROM alert_definitions WHERE name = 'invoice_postponed'),
            'initial',
            ':warning: *Invoice postponed*\n\nProject: *{project_name}*\nOriginal due date: {due_date}\nNew date: {new_date}\nReason: {reason}\n\n<{detail_url}|View invoice detail>',
            true
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM message_templates
        WHERE alert_definition_id = (SELECT id FROM alert_definitions WHERE name = 'invoice_postponed')
    """)
    op.execute("DELETE FROM alert_definitions WHERE name = 'invoice_postponed'")
