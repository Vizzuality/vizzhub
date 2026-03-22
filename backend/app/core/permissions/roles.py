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
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE,
        Action.TRACKER_MANAGE_ALL_REPORTS,
        Action.TRACKER_MANAGE_OWN_REPORTS,
    },
    "admin": {
        Action.ALL,
    },
}
