"""Role-to-permission mapping. Roles are defined in code; assignment is runtime."""

from app.core.permissions.actions import Action

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": {
        Action.SCORECARD_VIEW,
        Action.SCORECARD_EDIT_METRICS,
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE_OWN_REPORTS,
        Action.PROJECTS_VIEW,
        Action.EVENTS_VIEW,
        Action.DEVSTACK_VIEW,
    },
    "manager": {
        Action.PROJECTS_VIEW,
        Action.PROJECTS_MANAGE,
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE,
        Action.TRACKER_MANAGE_ALL_REPORTS,
        Action.TRACKER_MANAGE_OWN_REPORTS,
        Action.EVENTS_VIEW,
    },
    "playbook_editor": {
        Action.PLAYBOOK_EDIT,
    },
    "iso_docs_editor": {
        Action.ISO_DOCS_EDIT,
    },
    "events_manager": {
        Action.EVENTS_VIEW,
        Action.EVENTS_MANAGE,
    },
    "devstack_manager": {
        Action.DEVSTACK_VIEW,
        Action.DEVSTACK_MANAGE,
    },
    "admin": {
        Action.ALL,
    },
}
