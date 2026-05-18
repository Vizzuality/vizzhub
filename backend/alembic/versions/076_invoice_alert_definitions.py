"""Seed invoice_advance_warning + invoice_issue_reminder alert definitions.

Two daily Slack alerts driven by the worker:

- invoice_advance_warning — DMs the project manager 30 and 15 days before
  an invoice's effective scheduled date (scheduled or approved-postpone).
  config_json: {"days_before": [30, 15]}.
- invoice_issue_reminder — pings the configured issuer in the configured
  channel 1 day before. config_json:
  {"recipient_slack_user_id": "", "recipient_slack_channel_id": "",
   "days_before": 1}.

Dedup is handled by AlertNotificationDB metadata_json
({invoice_id, fired_for_date, alert_kind}); no schema change needed.
"""

from alembic import op

revision = "076_invoice_alert_definitions"
down_revision = "075_postponement_approval"
branch_labels = None
depends_on = None


ADVANCE_TEMPLATE = (
    ":calendar: Heads-up — invoice *{milestone}* on *{project_name}* "
    "(*{amount} {currency}*) is scheduled to be issued on *{due_date}* "
    "({days_until} days away). Review or request a postpone if needed.\n"
    "<{detail_url}|Open invoice>"
)

ISSUE_TEMPLATE = (
    "<@{issuer}> please issue on *{due_date}*: *{milestone}* on *{project_name}* "
    "— *{amount} {currency}*.\n<{detail_url}|Open invoice>"
)


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO alert_definitions (
            name, description, category, channel_type, schedule, is_enabled, config_json
        ) VALUES (
            'invoice_advance_warning',
            'DMs the project manager 30 and 15 days before an invoice is scheduled to be issued.',
            'business',
            'project',
            'daily',
            true,
            '{"days_before": [30, 15]}'::jsonb
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO message_templates (
            alert_definition_id, template_type, message_template, is_active
        ) VALUES (
            (SELECT id FROM alert_definitions WHERE name = 'invoice_advance_warning'),
            'initial',
            $tmpl${ADVANCE_TEMPLATE}$tmpl$,
            true
        )
        """
    )

    op.execute(
        """
        INSERT INTO alert_definitions (
            name, description, category, channel_type, schedule, is_enabled, config_json
        ) VALUES (
            'invoice_issue_reminder',
            'Pings the configured issuer in the configured Slack channel 1 day before an '
            'invoice is scheduled to be issued.',
            'business',
            'leadership',
            'daily',
            true,
            '{"recipient_slack_user_id": "", "recipient_slack_channel_id": "", "days_before": 1}'::jsonb
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO message_templates (
            alert_definition_id, template_type, message_template, is_active
        ) VALUES (
            (SELECT id FROM alert_definitions WHERE name = 'invoice_issue_reminder'),
            'initial',
            $tmpl${ISSUE_TEMPLATE}$tmpl$,
            true
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM message_templates WHERE alert_definition_id IN ("
        "SELECT id FROM alert_definitions "
        "WHERE name IN ('invoice_advance_warning', 'invoice_issue_reminder'))"
    )
    op.execute(
        "DELETE FROM alert_definitions "
        "WHERE name IN ('invoice_advance_warning', 'invoice_issue_reminder')"
    )
