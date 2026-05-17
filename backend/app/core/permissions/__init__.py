"""Permission system public API."""

from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.core.permissions.resolver import get_user_roles, resolve_permissions
from app.core.permissions.roles import ROLE_PERMISSIONS

__all__ = [
    "Action",
    "ROLE_PERMISSIONS",
    "get_user_roles",
    "require_permission",
    "resolve_permissions",
]
