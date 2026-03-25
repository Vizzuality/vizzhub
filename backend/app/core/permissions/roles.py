"""Role-to-permission mapping. Roles are defined in code; assignment is runtime."""

from app.core.permissions.actions import Action

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": {
        Action.SCORECARD_VIEW,
        Action.SCORECARD_EDIT_METRICS,
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE_OWN_REPORTS,
        Action.PROJECTS_VIEW,
    },
    "manager": {
        Action.PROJECTS_VIEW,
        Action.PROJECTS_MANAGE,
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE,
        Action.TRACKER_MANAGE_ALL_REPORTS,
        Action.TRACKER_MANAGE_OWN_REPORTS,
    },
    "playbook_editor": {
        Action.PLAYBOOK_EDIT,
    },
    "admin": {
        Action.ALL,
    },
}
