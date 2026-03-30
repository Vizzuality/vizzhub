"""Permission action constants for RBAC."""


class Action:
    """Permission string constants. Format: 'module:action'."""

    SCORECARD_VIEW = "scorecard:view"
    SCORECARD_EDIT_METRICS = "scorecard:edit_metrics"
    SCORECARD_CAPTURE = "scorecard:capture"
    SCORECARD_MANAGE = "scorecard:manage"

    TRACKER_VIEW = "tracker:view"
    TRACKER_MANAGE_OWN_REPORTS = "tracker:manage_own_reports"
    TRACKER_MANAGE_ALL_REPORTS = "tracker:manage_all_reports"
    TRACKER_MANAGE = "tracker:manage"

    ISO_VIEW = "iso:view"
    ISO_MANAGE = "iso:manage"

    PROJECTS_VIEW = "projects:view"
    PROJECTS_MANAGE = "projects:manage"

    PLAYBOOK_EDIT = "playbook:edit"

    ISO_DOCS_EDIT = "iso_docs:edit"

    ADMIN_USERS = "admin:users"
    ADMIN_JOBS = "admin:jobs"
    ADMIN_INTEGRATIONS = "admin:integrations"

    ALL = "*"
