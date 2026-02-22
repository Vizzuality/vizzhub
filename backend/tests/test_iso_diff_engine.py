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


class TestGroupMembershipDiff:
    def test_members_added_and_removed(self) -> None:
        current = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                    {"email": "c@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }
        previous = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                    {"email": "b@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")

        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 1
        assert membership[0]["subject_type"] == "group"
        assert membership[0]["subject_id"] == "team@test.com"
        assert "c@test.com" in membership[0]["current_value"]["added"]
        assert "b@test.com" in membership[0]["current_value"]["removed"]

    def test_no_membership_change(self) -> None:
        data = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }

        changes = compute_diff(data, data, "test.com")
        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 0

    def test_new_group_detected(self) -> None:
        current = {
            "users": [],
            "groups": [{"id": "g1", "email": "new@test.com", "name": "New"}],
            "group_members": {
                "new@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }
        previous = {
            "users": [],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")
        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 1
        assert "a@test.com" in membership[0]["current_value"]["added"]


class TestExternalMemberDiff:
    def test_new_external_detected(self) -> None:
        current = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                    {"email": "ext@vendor.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }
        previous = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "a@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }

        changes = compute_diff(current, previous, "test.com")
        externals = [c for c in changes if c["change_type"] == "new_external"]
        assert len(externals) == 1
        assert externals[0]["subject_type"] == "group"
        assert externals[0]["subject_id"] == "team@test.com"
        assert "ext@vendor.com" in externals[0]["current_value"]["external_added"]

    def test_existing_external_not_flagged(self) -> None:
        data = {
            "users": [],
            "groups": [{"id": "g1", "email": "team@test.com", "name": "Team"}],
            "group_members": {
                "team@test.com": [
                    {"email": "ext@vendor.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": [],
        }

        changes = compute_diff(data, data, "test.com")
        externals = [c for c in changes if c["change_type"] == "new_external"]
        assert len(externals) == 0
