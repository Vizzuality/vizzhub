"""Cerebro read role: an explicit allowlist of tables and columns.

Creates the login role cerebro (no password: on RDS it logs in with IAM tokens
through rds_iam) and grants SELECT only on the tables and columns that
app/core/cerebro_access.py allows. Any earlier access of the role to the
schema, including default privileges for future tables, is revoked first, so
this migration sets the whole access of the role.

The lists are copied here on purpose: a migration must not change when the
policy module changes later. A new grant needs a new migration.

Revision ID: 104_cerebro_read_role
Revises: 103_hash_mcp_refresh_tokens
"""

from collections.abc import Sequence

from alembic import op

revision: str = "104_cerebro_read_role"
down_revision: str | None = "103_hash_mcp_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "cerebro"

TABLE_GRANTS = (
    "alert_definitions",
    "alert_notifications",
    "alert_silences",
    "budget_lines",
    "capacity_plans",
    "clients",
    "config_parameters",
    "dependabot_alerts_tracked",
    "devstack_entries",
    "entity_terms",
    "event_attendees",
    "events",
    "exchange_rates",
    "functional_areas",
    "global_metrics",
    "integration_settings",
    "iso_doc_drive_mappings",
    "iso_doc_metadata",
    "iso_doc_nodes",
    "iso_doc_notes",
    "iso_doc_versions",
    "links",
    "message_templates",
    "metrics",
    "non_staff_costs",
    "playbook_nodes",
    "playbook_page_versions",
    "playbook_publish_log",
    "portfolio_profile",
    "programs",
    "progress_reports",
    "projects",
    "registry_attachments",
    "registry_rows",
    "registry_types",
    "reporting_periods",
    "roles",
    "scheduled_job_runs",
    "taxonomies",
    "taxonomy_terms",
    "tracker_project_settings",
    "user_roles",
)

COLUMN_GRANTS = {
    "users": (
        "id",
        "email",
        "name",
        "first_name",
        "last_name",
        "picture",
        "functional_area_id",
        "dedication",
        "slack_user_id",
        "slack_display_name",
        "active",
        "requires_project_reporting",
        "last_login_at",
        "created_at",
        "updated_at",
    ),
    "reports": (
        "id",
        "user_id",
        "reporting_period_id",
        "estimated",
        "created_at",
        "updated_at",
    ),
    "report_parts": (
        "id",
        "report_id",
        "project_id",
        "functional_area_id",
        "percentage",
        "days",
        "created_at",
        "updated_at",
    ),
}

_IF_ROLE = f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN"

_REVOKE_ALL = f"""
DO $$
BEGIN
    {_IF_ROLE}
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE};
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {ROLE};
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'REVOKE ALL ON TABLES FROM {ROLE}',
            current_user
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON TABLES FROM {ROLE}',
            current_user
        );
    END IF;
END $$
"""


def _grant_statements() -> str:
    statements = [
        f"GRANT USAGE ON SCHEMA public TO {ROLE};",
        f"GRANT SELECT ON TABLE {', '.join(TABLE_GRANTS)} TO {ROLE};",
    ]
    statements += [
        f"GRANT SELECT ({', '.join(columns)}) ON TABLE {table} TO {ROLE};"
        for table, columns in COLUMN_GRANTS.items()
    ]
    return "\n        ".join(statements)


def upgrade() -> None:
    # Creating a role needs CREATEROLE: the RDS master user has it, a local
    # development user usually does not. Without it the role is skipped.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                IF (SELECT rolsuper OR rolcreaterole FROM pg_roles
                    WHERE rolname = current_user) THEN
                    CREATE ROLE {ROLE} LOGIN;
                ELSE
                    RAISE NOTICE 'role {ROLE} not created: no CREATEROLE';
                END IF;
            END IF;
        END $$
        """
    )
    # rds_iam only exists on RDS; elsewhere the role has no way to log in.
    op.execute(
        f"""
        DO $$
        BEGIN
            {_IF_ROLE}
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rds_iam') THEN
                    GRANT rds_iam TO {ROLE};
                END IF;
            END IF;
        END $$
        """
    )
    op.execute(_REVOKE_ALL)
    op.execute(
        f"""
        DO $$
        BEGIN
            {_IF_ROLE}
                {_grant_statements()}
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    # The role is kept: Cerebro may own objects (its own database) on the instance.
    op.execute(_REVOKE_ALL)
