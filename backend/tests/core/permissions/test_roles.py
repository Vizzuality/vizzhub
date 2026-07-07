"""Tests for role-permission mapping."""

from app.core.permissions.actions import Action
from app.core.permissions.roles import ROLE_PERMISSIONS


def test_required_roles_exist():
    assert "user" in ROLE_PERMISSIONS
    assert "manager" in ROLE_PERMISSIONS
    assert "admin" in ROLE_PERMISSIONS


def test_admin_has_wildcard():
    assert Action.ALL in ROLE_PERMISSIONS["admin"]


def test_user_has_base_permissions():
    user_perms = ROLE_PERMISSIONS["user"]
    assert Action.SCORECARD_VIEW in user_perms
    assert Action.PROJECTS_VIEW in user_perms
    assert Action.TRACKER_VIEW in user_perms
    assert Action.TRACKER_MANAGE_OWN_REPORTS in user_perms
    assert Action.DEVSTACK_VIEW in user_perms


def test_user_cannot_manage_tracker():
    user_perms = ROLE_PERMISSIONS["user"]
    assert Action.TRACKER_MANAGE not in user_perms
    assert Action.TRACKER_MANAGE_ALL_REPORTS not in user_perms


def test_manager_has_tracker_management():
    manager_perms = ROLE_PERMISSIONS["manager"]
    assert Action.TRACKER_MANAGE in manager_perms
    assert Action.TRACKER_MANAGE_ALL_REPORTS in manager_perms
    assert Action.TRACKER_MANAGE_OWN_REPORTS in manager_perms


def test_devstack_manager_grants_view_and_manage():
    perms = ROLE_PERMISSIONS["devstack_manager"]
    assert Action.DEVSTACK_VIEW in perms
    assert Action.DEVSTACK_MANAGE in perms


def test_portfolio_view_for_all_base_roles():
    assert Action.PORTFOLIO_VIEW in ROLE_PERMISSIONS["user"]
    assert Action.PORTFOLIO_VIEW in ROLE_PERMISSIONS["manager"]


def test_portfolio_manage_only_via_portfolio_manager():
    perms = ROLE_PERMISSIONS["portfolio_manager"]
    assert Action.PORTFOLIO_VIEW in perms
    assert Action.PORTFOLIO_MANAGE in perms
    assert Action.PORTFOLIO_MANAGE not in ROLE_PERMISSIONS["user"]
    assert Action.PORTFOLIO_MANAGE not in ROLE_PERMISSIONS["manager"]


def test_all_permission_values_are_valid_actions():
    valid_actions = {getattr(Action, attr) for attr in dir(Action) if not attr.startswith("_")}
    for role, perms in ROLE_PERMISSIONS.items():
        for perm in perms:
            assert perm in valid_actions, f"Role '{role}' has unknown permission '{perm}'"
