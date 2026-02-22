# Phase 5: Diff Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a deterministic diff engine that compares two snapshots and produces change records (new users, removed users, role changes, group membership changes, new externals). Wire it into the capture flow to auto-populate review actions.

**Architecture:** Pure function `compute_diff(current_data, previous_data, domain)` returns a list of change dicts. Separate functions `build_diff_summary()` and `create_review_actions()` handle aggregation and persistence. The capture endpoint in `snapshots.py` calls the diff engine after creating the review.

**Tech Stack:** Python (pure functions + SQLAlchemy for persistence), pytest

---

### Task 1: Diff engine skeleton — user diffs and admin diffs

**Files:**
- Create: `backend/app/modules/iso/services/diff_engine.py`
- Create: `backend/tests/test_iso_diff_engine.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_diff_engine.py -v --no-header -q`
Expected: FAIL with ImportError

**Step 3: Write the implementation**

```python
"""Diff engine for comparing access snapshots."""

from typing import Any


def compute_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
    domain: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    changes.extend(_diff_users(current_data, previous_data))
    changes.extend(_diff_admins(current_data, previous_data))

    return changes


def _diff_users(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_emails = {u["email"]: u for u in current["users"]}
    previous_emails = {u["email"]: u for u in previous["users"]}
    changes: list[dict[str, Any]] = []

    for email in current_emails.keys() - previous_emails.keys():
        u = current_emails[email]
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": u.get("name", ""),
            "change_type": "new_user",
            "previous_value": None,
            "current_value": {"email": email, "name": u.get("name", "")},
        })

    for email in previous_emails.keys() - current_emails.keys():
        u = previous_emails[email]
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": u.get("name", ""),
            "change_type": "removed_user",
            "previous_value": {"email": email, "name": u.get("name", "")},
            "current_value": None,
        })

    return changes


def _diff_admins(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_admin_emails = {
        ra["user_email"] for ra in current["role_assignments"]
    }
    previous_admin_emails = {
        ra["user_email"] for ra in previous["role_assignments"]
    }

    current_users = {u["email"]: u for u in current["users"]}
    previous_users = {u["email"]: u for u in previous["users"]}
    all_users = {**previous_users, **current_users}
    changes: list[dict[str, Any]] = []

    for email in current_admin_emails - previous_admin_emails:
        user = all_users.get(email, {})
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": user.get("name", ""),
            "change_type": "role_change",
            "previous_value": {"is_admin": False},
            "current_value": {"is_admin": True},
        })

    for email in previous_admin_emails - current_admin_emails:
        user = all_users.get(email, {})
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": user.get("name", ""),
            "change_type": "role_change",
            "previous_value": {"is_admin": True},
            "current_value": {"is_admin": False},
        })

    return changes
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_diff_engine.py -v --no-header -q`
Expected: 5 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/diff_engine.py tests/test_iso_diff_engine.py
git commit -m "feat(iso): add diff engine with user and admin diffs"
```

---

### Task 2: Group membership diff and external member detection

**Files:**
- Modify: `backend/app/modules/iso/services/diff_engine.py`
- Modify: `backend/tests/test_iso_diff_engine.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_diff_engine.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_diff_engine.py::TestGroupMembershipDiff tests/test_iso_diff_engine.py::TestExternalMemberDiff -v --no-header -q`
Expected: FAIL (functions not called or not returning these types)

**Step 3: Add to `diff_engine.py`**

Update `compute_diff` to call the new functions:

```python
def compute_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
    domain: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    changes.extend(_diff_users(current_data, previous_data))
    changes.extend(_diff_admins(current_data, previous_data))
    changes.extend(_diff_group_members(current_data, previous_data))
    changes.extend(_diff_externals(current_data, previous_data, domain))

    return changes
```

Add the new functions:

```python
def _diff_group_members(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})
    current_groups = {g["email"]: g for g in current.get("groups", [])}
    all_group_emails = set(current_members.keys()) | set(previous_members.keys())
    changes: list[dict[str, Any]] = []

    for group_email in all_group_emails:
        curr_emails = {m["email"] for m in current_members.get(group_email, [])}
        prev_emails = {m["email"] for m in previous_members.get(group_email, [])}
        added = curr_emails - prev_emails
        removed = prev_emails - curr_emails

        if added or removed:
            group = current_groups.get(group_email, {})
            changes.append({
                "subject_type": "group",
                "subject_id": group_email,
                "subject_label": group.get("name", ""),
                "change_type": "group_membership_change",
                "previous_value": {"members": sorted(prev_emails)},
                "current_value": {
                    "added": sorted(added),
                    "removed": sorted(removed),
                },
            })

    return changes


def _diff_externals(
    current: dict[str, Any],
    previous: dict[str, Any],
    domain: str,
) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})
    current_groups = {g["email"]: g for g in current.get("groups", [])}
    changes: list[dict[str, Any]] = []

    for group_email, members in current_members.items():
        curr_external = {
            m["email"]
            for m in members
            if m.get("email") and not m["email"].endswith(f"@{domain}")
        }
        prev_external = {
            m["email"]
            for m in previous_members.get(group_email, [])
            if m.get("email") and not m["email"].endswith(f"@{domain}")
        }
        new_external = curr_external - prev_external

        if new_external:
            group = current_groups.get(group_email, {})
            changes.append({
                "subject_type": "group",
                "subject_id": group_email,
                "subject_label": group.get("name", ""),
                "change_type": "new_external",
                "previous_value": None,
                "current_value": {"external_added": sorted(new_external)},
            })

    return changes
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_diff_engine.py -v --no-header -q`
Expected: 10 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/diff_engine.py tests/test_iso_diff_engine.py
git commit -m "feat(iso): add group membership and external member diffs"
```

---

### Task 3: build_diff_summary() and create_review_actions()

**Files:**
- Modify: `backend/app/modules/iso/services/diff_engine.py`
- Modify: `backend/tests/test_iso_diff_engine.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_diff_engine.py`:

```python
from uuid import uuid4

from app.modules.iso.services.diff_engine import build_diff_summary, create_review_actions
from app.modules.iso.models.access_review_action import AccessReviewActionDB


class TestBuildDiffSummary:
    def test_counts_by_change_type(self) -> None:
        changes = [
            {"change_type": "new_user", "subject_type": "user", "subject_id": "a@t.com"},
            {"change_type": "new_user", "subject_type": "user", "subject_id": "b@t.com"},
            {"change_type": "role_change", "subject_type": "user", "subject_id": "c@t.com"},
            {"change_type": "group_membership_change", "subject_type": "group", "subject_id": "g@t.com"},
        ]

        summary = build_diff_summary(changes)
        assert summary["total_changes"] == 4
        assert summary["new_user"] == 2
        assert summary["role_change"] == 1
        assert summary["group_membership_change"] == 1

    def test_empty_changes(self) -> None:
        summary = build_diff_summary([])
        assert summary["total_changes"] == 0


class TestCreateReviewActions:
    @pytest.mark.asyncio
    async def test_creates_action_rows(self, db_session) -> None:
        from sqlalchemy import select

        review_id = uuid4()
        changes = [
            {
                "subject_type": "user",
                "subject_id": "a@test.com",
                "subject_label": "A",
                "change_type": "new_user",
                "previous_value": None,
                "current_value": {"email": "a@test.com"},
            },
            {
                "subject_type": "group",
                "subject_id": "team@test.com",
                "subject_label": "Team",
                "change_type": "group_membership_change",
                "previous_value": {"members": []},
                "current_value": {"added": ["b@test.com"], "removed": []},
            },
        ]

        await create_review_actions(db_session, review_id, changes)

        result = await db_session.execute(
            select(AccessReviewActionDB).where(
                AccessReviewActionDB.review_id == review_id
            )
        )
        actions = result.scalars().all()
        assert len(actions) == 2
        assert actions[0].subject_id == "a@test.com"
        assert actions[0].change_type == "new_user"
        assert actions[0].action_taken is None

    @pytest.mark.asyncio
    async def test_no_actions_for_empty_changes(self, db_session) -> None:
        from sqlalchemy import select

        review_id = uuid4()
        await create_review_actions(db_session, review_id, [])

        result = await db_session.execute(
            select(AccessReviewActionDB).where(
                AccessReviewActionDB.review_id == review_id
            )
        )
        actions = result.scalars().all()
        assert len(actions) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_diff_engine.py::TestBuildDiffSummary tests/test_iso_diff_engine.py::TestCreateReviewActions -v --no-header -q`
Expected: FAIL with ImportError

**Step 3: Add to `diff_engine.py`**

Add imports at top:

```python
from collections import Counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_review_action import AccessReviewActionDB
```

Add functions:

```python
def build_diff_summary(changes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(c["change_type"] for c in changes)
    return {
        "total_changes": len(changes),
        "new_user": counts.get("new_user", 0),
        "removed_user": counts.get("removed_user", 0),
        "role_change": counts.get("role_change", 0),
        "new_external": counts.get("new_external", 0),
        "group_membership_change": counts.get("group_membership_change", 0),
    }


async def create_review_actions(
    db: AsyncSession,
    review_id: UUID,
    changes: list[dict[str, Any]],
) -> None:
    for change in changes:
        action = AccessReviewActionDB(
            review_id=review_id,
            subject_type=change["subject_type"],
            subject_id=change["subject_id"],
            subject_label=change.get("subject_label"),
            change_type=change["change_type"],
            previous_value=change.get("previous_value"),
            current_value=change.get("current_value"),
        )
        db.add(action)
    await db.flush()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_diff_engine.py -v --no-header -q`
Expected: 14 passed

**Step 5: Commit**

```bash
git add app/modules/iso/services/diff_engine.py tests/test_iso_diff_engine.py
git commit -m "feat(iso): add build_diff_summary and create_review_actions"
```

---

### Task 4: Wire diff engine into capture endpoint

**Files:**
- Modify: `backend/app/modules/iso/api/snapshots.py`
- Modify: `backend/tests/test_iso_snapshots.py`

**Step 1: Write the failing test**

Add to `tests/test_iso_snapshots.py`:

```python
class TestCaptureWithDiff:
    @pytest.mark.asyncio
    async def test_capture_populates_diff_and_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        from sqlalchemy import select

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        previous = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={"domain": "empresa.com"},
            data={
                "users": [
                    {"id": "u1", "email": "a@empresa.com", "name": "A", "suspended": False, "org_unit_path": "/"},
                ],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
            summary={"total_users": 1},
        )
        db_session.add(previous)
        await db_session.flush()

        users_resp = MagicMock()
        users_resp.json.return_value = {
            "users": [
                {"id": "u1", "primaryEmail": "a@empresa.com", "name": {"fullName": "A"}, "suspended": False, "orgUnitPath": "/"},
                {"id": "u2", "primaryEmail": "new@empresa.com", "name": {"fullName": "New"}, "suspended": False, "orgUnitPath": "/"},
            ],
        }
        users_resp.raise_for_status = MagicMock()

        empty_resp = MagicMock()
        empty_resp.json.return_value = {}
        empty_resp.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[users_resp, empty_resp, empty_resp, empty_resp],
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == response.json()["id"]
            )
        )
        review = result.scalar_one()
        assert review.diff_summary is not None
        assert review.diff_summary["total_changes"] >= 1
        assert review.diff_summary["new_user"] >= 1

        from app.modules.iso.models.access_review_action import AccessReviewActionDB

        result = await db_session.execute(
            select(AccessReviewActionDB).where(
                AccessReviewActionDB.review_id == review.id
            )
        )
        actions = result.scalars().all()
        assert len(actions) >= 1
        new_user_actions = [a for a in actions if a.change_type == "new_user"]
        assert len(new_user_actions) >= 1

    @pytest.mark.asyncio
    async def test_first_snapshot_no_diff(
        self, client: AsyncClient, db_session
    ) -> None:
        from sqlalchemy import select

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "users": [
                {"id": "u1", "primaryEmail": "a@empresa.com", "name": {"fullName": "A"}, "suspended": False, "orgUnitPath": "/"},
            ],
            "groups": [],
            "members": [],
            "items": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == response.json()["id"]
            )
        )
        review = result.scalar_one()
        assert review.diff_summary is None
        assert review.previous_snapshot_id is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_snapshots.py::TestCaptureWithDiff -v --no-header -q`
Expected: FAIL (diff_summary not populated yet)

**Step 3: Update `snapshots.py` capture endpoint**

Add imports:

```python
from app.modules.iso.services.diff_engine import (
    build_diff_summary,
    compute_diff,
    create_review_actions,
)
```

Update the capture endpoint after review creation (after `await db.flush()`):

```python
    # Run diff engine if there's a previous snapshot
    if previous:
        domain = snapshot.source_metadata.get("domain", "")
        changes = compute_diff(snapshot.data, previous.data, domain)
        review.diff_summary = build_diff_summary(changes)
        await create_review_actions(db, review.id, changes)
        await db.flush()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: 13 passed

**Step 5: Commit**

```bash
git add app/modules/iso/api/snapshots.py tests/test_iso_snapshots.py
git commit -m "feat(iso): wire diff engine into capture flow"
```

---

### Task 5: Full regression test + lint

**Step 1: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: 904+ passed (890 existing + 14 new diff engine tests)

**Step 2: Run lint**

Run: `ruff check app/modules/iso/ tests/test_iso_diff_engine.py tests/test_iso_snapshots.py && black --check app/modules/iso/ tests/test_iso_diff_engine.py tests/test_iso_snapshots.py`
Expected: All checks passed. If Black fails, run `black` and commit the fix.
