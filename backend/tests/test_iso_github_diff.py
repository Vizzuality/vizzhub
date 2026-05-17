"""Tests for GitHub-specific ISO diff engine."""

from app.modules.iso.services.diff_engine import build_diff_summary, compute_diff
from app.modules.iso.services.diff_github import compute_github_diff


def _empty_github_data() -> dict:
    return {
        "members": [],
        "outside_collaborators": [],
        "teams": [],
        "team_members": {},
    }


class TestMemberDiff:
    def test_diff_members_new(self) -> None:
        current = _empty_github_data()
        current["members"] = [
            {"login": "alice", "name": "Alice", "role": "admin"},
            {"login": "bob", "name": "Bob", "role": "member"},
        ]
        previous = _empty_github_data()
        previous["members"] = [
            {"login": "alice", "name": "Alice", "role": "admin"},
        ]

        changes = compute_github_diff(current, previous)

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 1
        assert new_users[0]["subject_id"] == "bob"
        assert new_users[0]["subject_type"] == "user"
        assert new_users[0]["subject_label"] == "Bob"
        assert new_users[0]["current_value"] == {"login": "bob", "role": "member"}
        assert new_users[0]["previous_value"] is None

    def test_diff_members_uses_login_when_no_name(self) -> None:
        current = _empty_github_data()
        current["members"] = [{"login": "noname", "role": "member"}]
        previous = _empty_github_data()

        changes = compute_github_diff(current, previous)
        assert changes[0]["subject_label"] == "noname"

    def test_diff_members_removed(self) -> None:
        current = _empty_github_data()
        current["members"] = [
            {"login": "alice", "role": "admin"},
        ]
        previous = _empty_github_data()
        previous["members"] = [
            {"login": "alice", "role": "admin"},
            {"login": "bob", "role": "member"},
        ]

        changes = compute_github_diff(current, previous)

        removed = [c for c in changes if c["change_type"] == "removed_user"]
        assert len(removed) == 1
        assert removed[0]["subject_id"] == "bob"
        assert removed[0]["previous_value"] == {"login": "bob", "role": "member"}
        assert removed[0]["current_value"] is None

    def test_diff_members_no_changes(self) -> None:
        data = _empty_github_data()
        data["members"] = [
            {"login": "alice", "role": "admin"},
            {"login": "bob", "role": "member"},
        ]

        changes = compute_github_diff(data, data)

        user_changes = [c for c in changes if c["change_type"] in ("new_user", "removed_user")]
        assert len(user_changes) == 0


class TestMemberRoleDiff:
    def test_diff_member_roles_changed(self) -> None:
        current = _empty_github_data()
        current["members"] = [{"login": "alice", "name": "Alice", "role": "admin"}]
        previous = _empty_github_data()
        previous["members"] = [{"login": "alice", "name": "Alice", "role": "member"}]

        changes = compute_github_diff(current, previous)

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 1
        assert role_changes[0]["subject_id"] == "alice"
        assert role_changes[0]["subject_label"] == "Alice"
        assert role_changes[0]["previous_value"] == {"role": "member"}
        assert role_changes[0]["current_value"] == {"role": "admin"}

    def test_diff_member_roles_no_change(self) -> None:
        data = _empty_github_data()
        data["members"] = [
            {"login": "alice", "role": "admin"},
            {"login": "bob", "role": "member"},
        ]

        changes = compute_github_diff(data, data)

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 0


class TestOutsideCollaboratorDiff:
    def test_diff_outside_collaborators_new(self) -> None:
        current = _empty_github_data()
        current["outside_collaborators"] = [{"login": "ext-user", "name": "External"}]
        previous = _empty_github_data()

        changes = compute_github_diff(current, previous)

        externals = [c for c in changes if c["change_type"] == "new_external"]
        assert len(externals) == 1
        assert externals[0]["subject_id"] == "ext-user"
        assert externals[0]["subject_label"] == "External"
        assert externals[0]["subject_type"] == "user"
        assert externals[0]["current_value"] == {"login": "ext-user"}

    def test_diff_outside_collaborators_removed(self) -> None:
        current = _empty_github_data()
        previous = _empty_github_data()
        previous["outside_collaborators"] = [{"login": "ext-user"}]

        changes = compute_github_diff(current, previous)

        removed = [c for c in changes if c["change_type"] == "removed_external"]
        assert len(removed) == 1
        assert removed[0]["subject_id"] == "ext-user"
        assert removed[0]["previous_value"] == {"login": "ext-user"}
        assert removed[0]["current_value"] is None

    def test_diff_outside_collaborators_no_changes(self) -> None:
        data = _empty_github_data()
        data["outside_collaborators"] = [{"login": "ext-user"}]

        changes = compute_github_diff(data, data)

        ext_changes = [
            c for c in changes if c["change_type"] in ("new_external", "removed_external")
        ]
        assert len(ext_changes) == 0


class TestTeamMemberDiff:
    def test_diff_team_members_added(self) -> None:
        current = _empty_github_data()
        current["teams"] = [{"slug": "backend", "name": "Backend Team"}]
        current["team_members"] = {
            "backend": [{"login": "alice"}, {"login": "bob"}],
        }
        previous = _empty_github_data()
        previous["teams"] = [{"slug": "backend", "name": "Backend Team"}]
        previous["team_members"] = {
            "backend": [{"login": "alice"}],
        }

        changes = compute_github_diff(current, previous)

        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 1
        assert membership[0]["subject_type"] == "group"
        assert membership[0]["subject_id"] == "backend"
        assert membership[0]["subject_label"] == "Backend Team"
        assert "bob" in membership[0]["current_value"]["added"]
        assert membership[0]["current_value"]["removed"] == []

    def test_diff_team_members_removed(self) -> None:
        current = _empty_github_data()
        current["teams"] = [{"slug": "backend", "name": "Backend Team"}]
        current["team_members"] = {
            "backend": [{"login": "alice"}],
        }
        previous = _empty_github_data()
        previous["teams"] = [{"slug": "backend", "name": "Backend Team"}]
        previous["team_members"] = {
            "backend": [{"login": "alice"}, {"login": "bob"}],
        }

        changes = compute_github_diff(current, previous)

        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 1
        assert "bob" in membership[0]["current_value"]["removed"]
        assert membership[0]["current_value"]["added"] == []

    def test_diff_team_members_no_changes(self) -> None:
        data = _empty_github_data()
        data["teams"] = [{"slug": "backend", "name": "Backend Team"}]
        data["team_members"] = {
            "backend": [{"login": "alice"}, {"login": "bob"}],
        }

        changes = compute_github_diff(data, data)

        membership = [c for c in changes if c["change_type"] == "group_membership_change"]
        assert len(membership) == 0


class TestComputeDiffDispatch:
    def test_compute_diff_dispatch_github(self) -> None:
        current = _empty_github_data()
        current["members"] = [
            {"login": "alice", "role": "admin"},
            {"login": "bob", "role": "member"},
        ]
        previous = _empty_github_data()
        previous["members"] = [
            {"login": "alice", "role": "admin"},
        ]

        changes = compute_diff(current, previous, domain="", provider="github")

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 1
        assert new_users[0]["subject_id"] == "bob"


class TestIntegration:
    def test_compute_github_diff_integration(self) -> None:
        """Full diff with multiple change types simultaneously."""
        previous = {
            "members": [
                {"login": "alice", "role": "member"},
                {"login": "charlie", "role": "member"},
            ],
            "outside_collaborators": [{"login": "old-vendor"}],
            "teams": [{"slug": "backend", "name": "Backend"}],
            "team_members": {
                "backend": [{"login": "alice"}, {"login": "charlie"}],
            },
        }
        current = {
            "members": [
                {"login": "alice", "role": "admin"},
                {"login": "bob", "role": "member"},
            ],
            "outside_collaborators": [{"login": "new-vendor"}],
            "teams": [{"slug": "backend", "name": "Backend"}],
            "team_members": {
                "backend": [{"login": "alice"}, {"login": "bob"}],
            },
        }

        changes = compute_github_diff(current, previous)
        change_types = [c["change_type"] for c in changes]

        assert "new_user" in change_types
        assert "removed_user" in change_types
        assert "role_change" in change_types
        assert "new_external" in change_types
        assert "removed_external" in change_types
        assert "group_membership_change" in change_types
        assert len(changes) == 6

    def test_build_diff_summary_with_github_types(self) -> None:
        changes = [
            {
                "change_type": "new_user",
                "subject_type": "user",
                "subject_id": "bob",
            },
            {
                "change_type": "removed_external",
                "subject_type": "user",
                "subject_id": "old-vendor",
            },
            {
                "change_type": "group_membership_change",
                "subject_type": "group",
                "subject_id": "backend",
            },
        ]

        summary = build_diff_summary(changes)

        assert summary["total_changes"] == 3
        assert summary["new_user"] == 1
        assert summary["removed_external"] == 1
        assert summary["group_membership_change"] == 1
        assert summary["removed_user"] == 0
        assert summary["role_change"] == 0
        assert summary["new_external"] == 0
