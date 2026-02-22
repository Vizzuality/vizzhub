"""Tests for ISO diff engine."""

import pytest

from app.modules.iso.services.diff_engine import compute_diff


class TestUserDiff:
    def test_new_user(self) -> None:
        current = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
                {"id": "u2", "email": "b@test.com", "name": "B", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }
        previous = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 1
        assert new_users[0]["subject_id"] == "b@test.com"
        assert new_users[0]["subject_type"] == "user"
        assert new_users[0]["subject_label"] == "B"

    def test_removed_user(self) -> None:
        current = {
            "users": [],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }
        previous = {
            "users": [
                {"id": "u1", "email": "gone@test.com", "name": "Gone", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")

        removed = [c for c in changes if c["change_type"] == "removed_user"]
        assert len(removed) == 1
        assert removed[0]["subject_id"] == "gone@test.com"

    def test_no_user_changes(self) -> None:
        data = {
            "users": [{"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"}],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }

        changes = compute_diff(data, data, "test.com")
        user_changes = [c for c in changes if c["change_type"] in ("new_user", "removed_user")]
        assert len(user_changes) == 0


class TestAdminDiff:
    def test_new_admin(self) -> None:
        current = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [
                {"user_id": "u1", "user_email": "a@test.com", "role_id": "1", "role_name": "Super Admin"},
            ],
        }
        previous = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 1
        assert role_changes[0]["subject_id"] == "a@test.com"
        assert role_changes[0]["current_value"] == {"is_admin": True}
        assert role_changes[0]["previous_value"] == {"is_admin": False}

    def test_removed_admin(self) -> None:
        current = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }
        previous = {
            "users": [
                {"id": "u1", "email": "a@test.com", "name": "A", "suspended": False, "org_unit_path": "/"},
            ],
            "groups": [],
            "group_members": {},
            "role_assignments": [
                {"user_id": "u1", "user_email": "a@test.com", "role_id": "1", "role_name": "Super Admin"},
            ],
        }

        changes = compute_diff(current, previous, "test.com")

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 1
        assert role_changes[0]["current_value"] == {"is_admin": False}
        assert role_changes[0]["previous_value"] == {"is_admin": True}
