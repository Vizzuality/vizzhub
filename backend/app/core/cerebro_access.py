"""Read access of the Cerebro role to the hub database: an explicit allowlist.

This module is the policy; the grants themselves ship as Alembic migrations.
To change what Cerebro reads, edit the lists here and add a migration that
applies the change. Nothing is granted by default: a new table stays hidden
until it is added to TABLE_GRANTS on purpose.
"""

from __future__ import annotations

CEREBRO_ROLE = "cerebro"

TABLE_GRANTS: tuple[str, ...] = (
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

COLUMN_GRANTS: dict[str, tuple[str, ...]] = {
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

# The rate band of a person, their mood and feedback, and the cost of a report
# part (the rate can be derived from it) stay private.
EXCLUDED_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("rate_id",),
    "reports": ("mood", "feedback_text"),
    "report_parts": ("cost",),
}

NOT_GRANTED: tuple[str, ...] = (
    # Credentials and auth
    "mcp_oauth_clients",
    "mcp_oauth_codes",
    "mcp_oauth_refresh_tokens",
    "oauth_tokens",
    "oauth_states",
    # Private by design
    "anonymous_feedback",
    # Security and operations
    "access_snapshots",
    "access_reviews",
    "access_review_actions",
    "jobs",
    # Financial and commercial
    "accrual_cells",
    "accrual_excel_rows",
    "accrual_import_runs",
    "accrual_line_projects",
    "accrual_lines",
    "accrual_periods",
    "invoices",
    "invoice_postponements",
    "rates",
)
