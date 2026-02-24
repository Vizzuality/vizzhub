# ISO Export + Modular Migration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ISO access review Excel export and migrate the export system to modular architecture.

**Architecture:** Shared XLSX helpers move to `app/core/services/`. Scorecard export moves to `app/modules/scorecard/`. New ISO export lives in `app/modules/iso/`. Frontend gets export buttons on both list and detail pages.

**Tech Stack:** openpyxl (existing), FastAPI, React, TanStack Query

**Design doc:** `docs/plans/2026-02-24-iso-export-design.md`

---

## Phase 1: Modular Migration (Backend)

### Task 1: Move shared export helpers to core

**Files:**
- Create: `backend/app/core/services/__init__.py`
- Create: `backend/app/core/services/export_helpers.py`
- Delete: `backend/app/services/export_helpers.py`

**Step 1: Create `app/core/services/__init__.py`**

Empty file.

**Step 2: Create `app/core/services/export_helpers.py`**

Copy the generic parts from `app/services/export_helpers.py`. Include:
- All fill/font/border constants (lines 13-39): `GREEN_FILL`, `YELLOW_FILL`, `RED_FILL`, subtle variants, `HEADER_FILL`, `HEADER_FONT`, `HEADER_ALIGNMENT`, `DIM_FILL`, `DIM_FONT`, `SCORE_FONT`, `SCORE_FILL`, `THIN_BORDER`, threshold defaults
- Generic functions (lines 45-113): `apply_score_traffic_light`, `apply_indicator_traffic_light`, `apply_header_style`, `apply_row_style`, `format_month_header`, `set_column_widths`, `freeze_panes`
- New standalone function `save_to_bytes(wb) -> BytesIO` (extracted from `ExportService._save_to_bytes`)

Do NOT include: `create_methodology_sheet`, `_get_threshold`, `_safe_get_target`, `_safe_get_weight` — these are scorecard-specific and depend on `ScoringConfig` and `export_definitions`.

The imports should only reference `openpyxl` — no app-specific imports.

**Step 3: Delete `app/services/export_helpers.py`**

Remove the old file entirely.

**Step 4: Update imports in consumers**

Update `app/services/export_service.py` line 17: change `from app.services.export_helpers import ...` to `from app.core.services.export_helpers import ...`.

The scorecard-specific functions (`create_methodology_sheet`, `_get_threshold`, `_safe_get_target`, `_safe_get_weight`) should be moved inline into `export_service.py` or into a local `_helpers.py` within the scorecard module. Since we're about to move the export service in Task 2, just inline them temporarily — we'll put them in the right place during the move.

Actually, simpler approach: move the whole `export_helpers.py` to core, but split `create_methodology_sheet` (and its private helpers `_get_threshold`, `_safe_get_target`, `_safe_get_weight`) out into the scorecard module in Task 2. For now, keep `create_methodology_sheet` in the core file temporarily — it'll move in Task 2.

So for this task:
1. Copy `app/services/export_helpers.py` → `app/core/services/export_helpers.py`
2. Add `save_to_bytes` function to the new file
3. Delete `app/services/export_helpers.py`
4. Update import in `app/services/export_service.py`: `from app.core.services.export_helpers import ...`
5. Update import in `backend/tests/test_export_helpers.py`: `from app.core.services.export_helpers import ...`

**Step 5: Run tests**

```bash
cd backend && pytest tests/test_export_helpers.py tests/test_export_service.py tests/test_export_api.py -v
```

Expected: All pass.

**Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move export helpers to app/core/services"
```

---

### Task 2: Create scorecard module and move export service

**Files:**
- Create: `backend/app/modules/scorecard/__init__.py`
- Create: `backend/app/modules/scorecard/router.py`
- Create: `backend/app/modules/scorecard/services/__init__.py`
- Create: `backend/app/modules/scorecard/services/export_service.py` (moved from `app/services/export_service.py`)
- Create: `backend/app/modules/scorecard/services/export_definitions.py` (moved from `app/services/export_definitions.py`)
- Create: `backend/app/modules/scorecard/services/export_helpers.py` (scorecard-specific helpers extracted from core)
- Create: `backend/app/modules/scorecard/api/__init__.py`
- Create: `backend/app/modules/scorecard/api/exports.py` (moved from `app/api/exports.py`)
- Delete: `backend/app/services/export_service.py`
- Delete: `backend/app/services/export_definitions.py`
- Delete: `backend/app/api/exports.py`
- Modify: `backend/app/main.py` (swap router mount)

**Step 1: Create directory structure**

```bash
mkdir -p backend/app/modules/scorecard/{services,api}
touch backend/app/modules/scorecard/__init__.py
touch backend/app/modules/scorecard/services/__init__.py
touch backend/app/modules/scorecard/api/__init__.py
```

**Step 2: Move export_definitions.py**

Move `app/services/export_definitions.py` → `app/modules/scorecard/services/export_definitions.py`. No import changes needed (file has no app imports).

**Step 3: Extract scorecard-specific helpers**

Create `app/modules/scorecard/services/export_helpers.py` with:
- `create_methodology_sheet(wb, config)` (from `app/core/services/export_helpers.py`)
- `_get_threshold(config, name, default)` (private helper)
- `_safe_get_target(config, indicator_key)` (private helper)
- `_safe_get_weight(config, dim_key, ind_key)` (private helper)

Imports:
```python
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.config import ScoringConfig
from app.core.services.export_helpers import (
    GREEN_FILL, GREEN_FILL_SUBTLE, YELLOW_FILL, YELLOW_FILL_SUBTLE,
    RED_FILL, RED_FILL_SUBTLE, apply_header_style, set_column_widths,
)
from app.modules.scorecard.services.export_definitions import (
    DIMENSION_DEFINITIONS, INDICATOR_DEFINITIONS,
)
```

Then remove `create_methodology_sheet`, `_get_threshold`, `_safe_get_target`, `_safe_get_weight` and the `from app.services.export_definitions` import from `app/core/services/export_helpers.py`.

**Step 4: Move export_service.py**

Move `app/services/export_service.py` → `app/modules/scorecard/services/export_service.py`.

Update imports inside:
```python
from app.modules.scorecard.services.export_definitions import DIMENSION_DEFINITIONS, get_metric_rows
from app.core.services.export_helpers import (
    DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD, THIN_BORDER,
    apply_header_style, apply_indicator_traffic_light, apply_row_style,
    apply_score_traffic_light, format_month_header, freeze_panes,
    set_column_widths, save_to_bytes,
)
from app.modules.scorecard.services.export_helpers import create_methodology_sheet
```

Replace `self._save_to_bytes(wb)` calls with `save_to_bytes(wb)` (the static method is now a standalone function in core).

**Step 5: Move exports API**

Move `app/api/exports.py` → `app/modules/scorecard/api/exports.py`.

Update import inside:
```python
from app.modules.scorecard.services.export_service import ExportService
```

**Step 6: Create scorecard router**

`app/modules/scorecard/router.py`:
```python
from fastapi import APIRouter

from app.modules.scorecard.api import exports as exports_router

router = APIRouter()
router.include_router(exports_router.router, prefix="/exports", tags=["exports"])
```

**Step 7: Update main.py**

Replace line 18 (`from app.api import exports as exports_router`) with:
```python
from app.modules.scorecard.router import router as scorecard_router
```

Replace line 197 (`app.include_router(exports_router.router, prefix="/api", tags=["exports"])`) with:
```python
app.include_router(scorecard_router, prefix="/api", tags=["scorecard"])
```

**Step 8: Delete old files**

```bash
rm backend/app/services/export_service.py
rm backend/app/services/export_definitions.py
rm backend/app/api/exports.py
```

**Step 9: Update test imports**

- `tests/test_export_service.py`: `from app.modules.scorecard.services.export_service import ExportService`
- `tests/test_export_definitions.py`: `from app.modules.scorecard.services.export_definitions import ...`
- `tests/test_export_helpers.py`: scorecard-specific test cases that test `create_methodology_sheet` should import from `app.modules.scorecard.services.export_helpers`; generic helper tests import from `app.core.services.export_helpers`

**Step 10: Run all tests**

```bash
cd backend && pytest tests/test_export_helpers.py tests/test_export_definitions.py tests/test_export_service.py tests/test_export_api.py -v
```

Expected: All pass. Then:

```bash
cd backend && pytest
```

Expected: Full suite passes (~830 tests).

**Step 11: Commit**

```bash
git add -A && git commit -m "refactor: move scorecard export to app/modules/scorecard"
```

---

## Phase 2: ISO Export Service (Backend)

### Task 3: Create IsoExportService

**Files:**
- Create: `backend/app/modules/iso/services/export_service.py`
- Create: `backend/tests/test_iso_export_service.py`

**Step 1: Write the test file**

`backend/tests/test_iso_export_service.py`:

```python
"""Tests for ISO export service — XLSX generation."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app.modules.iso.services.export_service import IsoExportService


def _make_snapshot(
    captured_at=None, domain="test.com", users=None, groups=None,
    group_members=None, role_assignments=None,
):
    """Build a fake snapshot dict matching AccessSnapshotDB shape."""
    return {
        "id": str(uuid4()),
        "provider": "google_workspace",
        "captured_at": captured_at or datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
        "data_version": "1",
        "source_metadata": {"domain": domain},
        "data": {
            "users": users or [
                {"id": "u1", "name": "Alice", "email": "alice@test.com",
                 "suspended": False, "org_unit_path": "/"},
            ],
            "groups": groups or [
                {"id": "g1", "name": "Engineering", "email": "eng@test.com"},
            ],
            "group_members": group_members or {
                "eng@test.com": [
                    {"email": "alice@test.com", "role": "MEMBER", "type": "USER"},
                ],
            },
            "role_assignments": role_assignments or [
                {"role_id": "r1", "user_id": "u1",
                 "role_name": "Super Admin", "user_email": "alice@test.com"},
            ],
        },
        "summary": {
            "total_users": 1, "total_admins": 1,
            "total_groups": 1, "external_members": 0,
        },
    }


def _make_review(status="signed", notes="All good", reviewer_email=None,
                 signed_by_email=None, signed_at=None, diff_summary=None):
    return {
        "id": str(uuid4()),
        "status": status,
        "scope": "All users and groups",
        "notes": notes,
        "reviewer_email": reviewer_email or "admin@test.com",
        "signed_by_email": signed_by_email or "admin@test.com",
        "signed_at": signed_at or datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        "diff_summary": diff_summary or {
            "total_changes": 1, "new_user": 1, "removed_user": 0,
            "role_change": 0, "new_external": 0, "group_membership_change": 0,
        },
    }


def _make_action(action_taken="accepted", justification="Approved"):
    return {
        "subject_label": "Alice",
        "subject_type": "user",
        "change_type": "new_user",
        "previous_value": None,
        "current_value": {"email": "alice@test.com"},
        "action_taken": action_taken,
        "justification": justification,
        "exception_until": None,
    }


class TestIsoExportService:
    def test_generates_workbook_with_summary_and_snapshot_tabs(self):
        service = IsoExportService()
        snapshot = _make_snapshot()
        review = _make_review()
        actions = [_make_action()]

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, review, actions)]
        )

        assert isinstance(output, BytesIO)
        wb = load_workbook(output)
        assert "Summary" in wb.sheetnames
        assert len(wb.sheetnames) == 2

    def test_summary_sheet_has_correct_columns(self):
        service = IsoExportService()
        snapshot = _make_snapshot()
        review = _make_review()

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, review, [])]
        )
        wb = load_workbook(output)
        ws = wb["Summary"]

        headers = [cell.value for cell in ws[1]]
        assert "Snapshot Date" in headers
        assert "Review Status" in headers
        assert "Signed Date" in headers

    def test_snapshot_tab_has_iso_header(self):
        service = IsoExportService()
        snapshot = _make_snapshot(domain="acme.com")
        review = _make_review()

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, review, [])]
        )
        wb = load_workbook(output)
        tab_name = [s for s in wb.sheetnames if s != "Summary"][0]
        ws = wb[tab_name]

        labels = [ws.cell(row=r, column=1).value for r in range(1, 12)]
        assert "Organization" in labels
        assert "Provider" in labels
        assert "Review Scope" in labels

        org_row = labels.index("Organization") + 1
        assert ws.cell(row=org_row, column=2).value == "acme.com"

    def test_snapshot_tab_has_users_table(self):
        service = IsoExportService()
        snapshot = _make_snapshot()
        review = _make_review()

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, review, [])]
        )
        wb = load_workbook(output)
        tab_name = [s for s in wb.sheetnames if s != "Summary"][0]
        ws = wb[tab_name]

        all_values = [
            ws.cell(row=r, column=c).value
            for r in range(1, ws.max_row + 1)
            for c in range(1, ws.max_column + 1)
        ]
        assert "alice@test.com" in all_values

    def test_snapshot_tab_has_actions_table(self):
        service = IsoExportService()
        snapshot = _make_snapshot()
        review = _make_review()
        actions = [_make_action()]

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, review, actions)]
        )
        wb = load_workbook(output)
        tab_name = [s for s in wb.sheetnames if s != "Summary"][0]
        ws = wb[tab_name]

        all_values = [
            ws.cell(row=r, column=c).value
            for r in range(1, ws.max_row + 1)
            for c in range(1, ws.max_column + 1)
        ]
        assert "Approved" in all_values

    def test_multiple_snapshots_generate_multiple_tabs(self):
        service = IsoExportService()
        snap1 = _make_snapshot(
            captured_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        snap2 = _make_snapshot(
            captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        review1 = _make_review()
        review2 = _make_review()

        output = service.export_snapshots(
            snapshots_with_reviews=[
                (snap1, review1, []),
                (snap2, review2, []),
            ]
        )
        wb = load_workbook(output)
        assert len(wb.sheetnames) == 3

    def test_snapshot_without_review(self):
        service = IsoExportService()
        snapshot = _make_snapshot()

        output = service.export_snapshots(
            snapshots_with_reviews=[(snapshot, None, [])]
        )
        wb = load_workbook(output)
        assert len(wb.sheetnames) == 2
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_iso_export_service.py -v
```

Expected: ImportError (module doesn't exist yet).

**Step 3: Implement IsoExportService**

Create `backend/app/modules/iso/services/export_service.py`:

```python
"""XLSX export service for ISO access review data."""

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from app.core.services.export_helpers import (
    HEADER_FILL,
    HEADER_FONT,
    HEADER_ALIGNMENT,
    THIN_BORDER,
    apply_header_style,
    save_to_bytes,
    set_column_widths,
)


class IsoExportService:
    """Generates XLSX exports for ISO access review snapshots."""

    def export_snapshots(
        self,
        snapshots_with_reviews: list[tuple[dict, dict | None, list[dict]]],
    ) -> BytesIO:
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        self._write_summary_sheet(ws, snapshots_with_reviews)

        for snapshot, review, actions in snapshots_with_reviews:
            captured = snapshot["captured_at"]
            if isinstance(captured, datetime):
                tab_name = f"Review {captured.strftime('%Y-%m-%d')}"
            else:
                tab_name = f"Review {str(captured)[:10]}"
            # Ensure unique tab names
            existing = [s for s in wb.sheetnames if s.startswith(tab_name)]
            if existing:
                tab_name = f"{tab_name} ({len(existing)})"
            tab = wb.create_sheet(tab_name)
            self._write_snapshot_tab(tab, snapshot, review, actions)

        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        return save_to_bytes(wb)

    def _write_summary_sheet(
        self,
        ws,
        snapshots_with_reviews: list[tuple[dict, dict | None, list[dict]]],
    ) -> None:
        headers = [
            "Snapshot Date", "Provider", "Total Users", "Total Admins",
            "Total Groups", "External Members", "Review Status",
            "Reviewer", "Signed By", "Signed Date",
        ]
        ws.append(headers)
        apply_header_style(ws, 1)

        for snapshot, review, _actions in snapshots_with_reviews:
            captured = snapshot["captured_at"]
            date_str = (
                captured.strftime("%Y-%m-%d %H:%M")
                if isinstance(captured, datetime)
                else str(captured)
            )
            summary = snapshot.get("summary", {})
            ws.append([
                date_str,
                snapshot.get("provider", ""),
                summary.get("total_users", 0),
                summary.get("total_admins", 0),
                summary.get("total_groups", 0),
                summary.get("external_members", 0),
                review["status"] if review else "",
                review.get("reviewer_email", "") if review else "",
                review.get("signed_by_email", "") if review else "",
                (
                    review["signed_at"].strftime("%Y-%m-%d %H:%M")
                    if review and review.get("signed_at")
                    and isinstance(review["signed_at"], datetime)
                    else str(review["signed_at"]) if review and review.get("signed_at")
                    else ""
                ),
            ])

        set_column_widths(ws, {
            "A": 20, "B": 18, "C": 12, "D": 12,
            "E": 12, "F": 16, "G": 14, "H": 25, "I": 25, "J": 20,
        })

    def _write_snapshot_tab(
        self, ws, snapshot: dict, review: dict | None, actions: list[dict],
    ) -> None:
        self._write_iso_header(ws, snapshot, review)
        ws.append([])

        if review and review.get("diff_summary"):
            self._write_diff_summary(ws, review["diff_summary"])
            ws.append([])

        if actions:
            self._write_actions_table(ws, actions)
            ws.append([])

        data = snapshot.get("data", {})
        self._write_users_table(ws, data.get("users", []))
        ws.append([])
        self._write_groups_table(ws, data.get("groups", []), data.get("group_members", {}))
        ws.append([])
        self._write_group_members_table(ws, data.get("group_members", {}))
        ws.append([])
        self._write_admins_table(ws, data.get("role_assignments", []))

        set_column_widths(ws, {"A": 25, "B": 30, "C": 20, "D": 20, "E": 18, "F": 18, "G": 16})

    def _write_iso_header(self, ws, snapshot: dict, review: dict | None) -> None:
        domain = snapshot.get("source_metadata", {}).get("domain", "")
        captured = snapshot["captured_at"]
        captured_str = (
            captured.strftime("%Y-%m-%d %H:%M UTC")
            if isinstance(captured, datetime)
            else str(captured)
        )

        header_rows = [
            ("Organization", domain),
            ("Provider", snapshot.get("provider", "")),
            ("Snapshot Date", captured_str),
            ("Review Scope", review["scope"] if review else "N/A"),
            ("Reviewer", review.get("reviewer_email", "") if review else ""),
            ("Status", review["status"] if review else "No review"),
            ("Signed By", review.get("signed_by_email", "") if review else ""),
            ("Signed Date", (
                review["signed_at"].strftime("%Y-%m-%d %H:%M UTC")
                if review and review.get("signed_at")
                and isinstance(review["signed_at"], datetime)
                else str(review["signed_at"]) if review and review.get("signed_at")
                else ""
            )),
            ("Notes", review.get("notes", "") if review else ""),
            ("Export Date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ]

        for label, value in header_rows:
            ws.append([label, value])
            row = ws.max_row
            ws.cell(row=row, column=1).font = Font(bold=True)

    def _write_diff_summary(self, ws, diff_summary: dict) -> None:
        ws.append(["Diff Summary"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        ws.append(["Change Type", "Count"])
        apply_header_style(ws, ws.max_row)

        mapping = [
            ("New Users", "new_user"),
            ("Removed Users", "removed_user"),
            ("Role Changes", "role_change"),
            ("New External", "new_external"),
            ("Group Changes", "group_membership_change"),
        ]
        for label, key in mapping:
            ws.append([label, diff_summary.get(key, 0)])

    def _write_actions_table(self, ws, actions: list[dict]) -> None:
        ws.append(["Actions"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        headers = [
            "Subject", "Type", "Change Type", "Details",
            "Action Taken", "Justification", "Exception Until",
        ]
        ws.append(headers)
        apply_header_style(ws, ws.max_row)

        for action in actions:
            details = ""
            prev = action.get("previous_value")
            curr = action.get("current_value")
            if prev:
                details += f"Previous: {prev}"
            if curr:
                if details:
                    details += " | "
                details += f"Current: {curr}"

            ws.append([
                action.get("subject_label", action.get("subject_id", "")),
                action.get("subject_type", ""),
                action.get("change_type", ""),
                details or "\u2014",
                action.get("action_taken", ""),
                action.get("justification", ""),
                str(action["exception_until"]) if action.get("exception_until") else "",
            ])

    def _write_users_table(self, ws, users: list[dict]) -> None:
        ws.append(["Users"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        ws.append(["Name", "Email", "Status", "Org Unit"])
        apply_header_style(ws, ws.max_row)

        for user in users:
            ws.append([
                user.get("name", ""),
                user.get("email", ""),
                "Suspended" if user.get("suspended") else "Active",
                user.get("org_unit_path", ""),
            ])

    def _write_groups_table(
        self, ws, groups: list[dict], group_members: dict[str, list],
    ) -> None:
        ws.append(["Groups"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        ws.append(["Name", "Email", "Members"])
        apply_header_style(ws, ws.max_row)

        for group in groups:
            email = group.get("email", "")
            members = group_members.get(email, [])
            ws.append([
                group.get("name", ""),
                email,
                len(members),
            ])

    def _write_group_members_table(self, ws, group_members: dict[str, list]) -> None:
        ws.append(["Group Members"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        ws.append(["Group Email", "Member Email", "Role", "Type"])
        apply_header_style(ws, ws.max_row)

        for group_email in sorted(group_members.keys()):
            for member in group_members[group_email]:
                ws.append([
                    group_email,
                    member.get("email", ""),
                    member.get("role", ""),
                    member.get("type", ""),
                ])

    def _write_admins_table(self, ws, role_assignments: list[dict]) -> None:
        ws.append(["Admins"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        ws.append(["Email", "Role Name"])
        apply_header_style(ws, ws.max_row)

        for ra in role_assignments:
            ws.append([
                ra.get("user_email", ""),
                ra.get("role_name", ""),
            ])
```

**Step 4: Run tests**

```bash
cd backend && pytest tests/test_iso_export_service.py -v
```

Expected: All pass.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(iso): add IsoExportService for XLSX generation"
```

---

### Task 4: Create ISO export API endpoints

**Files:**
- Create: `backend/app/modules/iso/api/exports.py`
- Modify: `backend/app/modules/iso/router.py` (add exports sub-router)
- Create: `backend/tests/test_iso_exports.py`

**Step 1: Write endpoint tests**

`backend/tests/test_iso_exports.py`:

```python
"""Tests for ISO export API endpoints."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from io import BytesIO

from app.models.user import UserDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _ensure_dev_user(db_session) -> None:
    from sqlalchemy import select
    result = await db_session.execute(
        select(UserDB).where(UserDB.id == DEV_USER_ID)
    )
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _make_snapshot(db_session, captured_at=None) -> AccessSnapshotDB:
    snapshot = AccessSnapshotDB(
        provider="google_workspace",
        captured_at=captured_at or datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
        data_version="1",
        source_metadata={"domain": "test.com"},
        data={
            "users": [{"id": "u1", "name": "Alice", "email": "alice@test.com",
                        "suspended": False, "org_unit_path": "/"}],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        },
        summary={"total_users": 1, "total_admins": 0, "total_groups": 0, "external_members": 0},
    )
    db_session.add(snapshot)
    await db_session.flush()
    return snapshot


async def _make_review(db_session, snapshot_id, status="draft") -> AccessReviewDB:
    review = AccessReviewDB(
        snapshot_id=snapshot_id,
        status=status,
        scope="All users and groups",
    )
    db_session.add(review)
    await db_session.flush()
    return review


class TestExportSnapshotRange:
    @pytest.mark.asyncio
    async def test_export_date_range(self, client: AsyncClient, db_session) -> None:
        await _ensure_dev_user(db_session)
        await _make_snapshot(db_session,
            captured_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
        await _make_snapshot(db_session,
            captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc))

        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-12-31"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == XLSX_CONTENT_TYPE

        wb = load_workbook(BytesIO(response.content))
        assert "Summary" in wb.sheetnames
        assert len(wb.sheetnames) == 3

    @pytest.mark.asyncio
    async def test_export_empty_range_returns_empty_summary(
        self, client: AsyncClient,
    ) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "2026-01-01", "to": "2026-12-31"},
        )
        assert response.status_code == 200
        wb = load_workbook(BytesIO(response.content))
        assert len(wb.sheetnames) == 1
        assert wb.sheetnames[0] == "Summary"

    @pytest.mark.asyncio
    async def test_export_invalid_date_format(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/exports/snapshots",
            params={"from": "bad-date", "to": "2026-12-31"},
        )
        assert response.status_code == 400


class TestExportSingleSnapshot:
    @pytest.mark.asyncio
    async def test_export_single_snapshot(
        self, client: AsyncClient, db_session,
    ) -> None:
        await _ensure_dev_user(db_session)
        snapshot = await _make_snapshot(db_session)

        response = await client.get(
            f"/api/iso/exports/snapshots/{snapshot.id}",
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == XLSX_CONTENT_TYPE

        wb = load_workbook(BytesIO(response.content))
        assert len(wb.sheetnames) == 2

    @pytest.mark.asyncio
    async def test_export_snapshot_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.get(f"/api/iso/exports/snapshots/{fake_id}")
        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_iso_exports.py -v
```

Expected: 404 (endpoints don't exist yet).

**Step 3: Implement the endpoints**

`backend/app/modules/iso/api/exports.py`:

```python
"""ISO export API endpoints."""

import re
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, DBSession, limiter
from app.models.user import UserDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.services.export_service import IsoExportService

router = APIRouter()

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _parse_date_param(value: str, param_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for '{param_name}': {value}. Use YYYY-MM-DD.",
        )


async def _build_export_data(
    db: AsyncSession, snapshots: list[AccessSnapshotDB],
) -> list[tuple[dict, dict | None, list[dict]]]:
    """Build the data tuples that IsoExportService expects."""
    user_cache: dict[UUID, str] = {}

    async def _resolve_email(user_id: UUID | None) -> str:
        if not user_id:
            return ""
        if user_id in user_cache:
            return user_cache[user_id]
        result = await db.execute(select(UserDB.email).where(UserDB.id == user_id))
        email = result.scalar_one_or_none() or ""
        user_cache[user_id] = email
        return email

    result = []
    for snapshot in snapshots:
        review_result = await db.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == snapshot.id
            )
        )
        review_db = review_result.scalar_one_or_none()

        review_dict = None
        actions_list: list[dict] = []

        if review_db:
            reviewer_email = await _resolve_email(review_db.reviewer_id)
            signed_by_email = await _resolve_email(review_db.signed_by)

            review_dict = {
                "id": str(review_db.id),
                "status": review_db.status,
                "scope": review_db.scope,
                "notes": review_db.notes,
                "reviewer_email": reviewer_email,
                "signed_by_email": signed_by_email,
                "signed_at": review_db.signed_at,
                "diff_summary": review_db.diff_summary,
            }

            actions_result = await db.execute(
                select(AccessReviewActionDB)
                .where(AccessReviewActionDB.review_id == review_db.id)
                .order_by(AccessReviewActionDB.created_at)
            )
            for action in actions_result.scalars().all():
                actions_list.append({
                    "subject_label": action.subject_label,
                    "subject_type": action.subject_type,
                    "subject_id": action.subject_id,
                    "change_type": action.change_type,
                    "previous_value": action.previous_value,
                    "current_value": action.current_value,
                    "action_taken": action.action_taken,
                    "justification": action.justification,
                    "exception_until": action.exception_until,
                })

        snapshot_dict = {
            "id": str(snapshot.id),
            "provider": snapshot.provider,
            "captured_at": snapshot.captured_at,
            "data_version": snapshot.data_version,
            "source_metadata": snapshot.source_metadata,
            "data": snapshot.data,
            "summary": snapshot.summary,
        }

        result.append((snapshot_dict, review_dict, actions_list))

    return result


@router.get("")
@limiter.limit("10/minute")
async def export_snapshot_range(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
) -> Response:
    start = _parse_date_param(from_date, "from")
    end = _parse_date_param(to_date, "to")

    if end < start:
        raise HTTPException(status_code=400, detail="'to' must not be before 'from'.")

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(AccessSnapshotDB)
        .where(AccessSnapshotDB.captured_at >= start_dt)
        .where(AccessSnapshotDB.captured_at <= end_dt)
        .order_by(AccessSnapshotDB.captured_at)
    )
    snapshots = list(result.scalars().all())

    export_data = await _build_export_data(db, snapshots)

    service = IsoExportService()
    output = service.export_snapshots(snapshots_with_reviews=export_data)

    filename = f"iso_access_review_{start}_{end}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{snapshot_id}")
@limiter.limit("10/minute")
async def export_single_snapshot(
    request: Request,
    snapshot_id: UUID,
    current_user: AdminUser,
    db: DBSession,
) -> Response:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    export_data = await _build_export_data(db, [snapshot])

    service = IsoExportService()
    output = service.export_snapshots(snapshots_with_reviews=export_data)

    captured_date = snapshot.captured_at.strftime("%Y-%m-%d")
    filename = f"iso_access_review_{captured_date}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Step 4: Wire into ISO router**

Add to `backend/app/modules/iso/router.py`:

```python
from app.modules.iso.api import exports as exports_router
# ...
router.include_router(
    exports_router.router, prefix="/exports/snapshots", tags=["iso-exports"]
)
```

**Step 5: Run tests**

```bash
cd backend && pytest tests/test_iso_exports.py tests/test_iso_export_service.py -v
```

Expected: All pass.

**Step 6: Run full backend suite**

```bash
cd backend && pytest
```

Expected: All pass.

**Step 7: Commit**

```bash
git add -A && git commit -m "feat(iso): add export API endpoints for snapshots"
```

---

## Phase 3: Frontend

### Task 5: Extract downloadBlob and add ISO export API + hook

**Files:**
- Create: `frontend/src/utils/file.ts`
- Modify: `frontend/src/hooks/useExport.ts` (import from shared util)
- Modify: `frontend/src/services/api/iso.ts` (add export methods)
- Create: `frontend/src/hooks/useIsoExport.ts`

**Step 1: Extract downloadBlob**

Create `frontend/src/utils/file.ts`:

```typescript
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

Update `frontend/src/hooks/useExport.ts`: replace the local `downloadBlob` function with:
```typescript
import { downloadBlob } from '../utils/file';
```
Remove the local `downloadBlob` function (lines 5-14).

**Step 2: Add ISO export API methods**

In `frontend/src/services/api/iso.ts`, add to the `isoApi` object:

```typescript
exportSnapshots: async (from: string, to: string): Promise<Blob> => {
  const response = await api.get('/iso/exports/snapshots', {
    params: { from, to },
    responseType: 'blob',
  });
  return response.data;
},

exportSnapshot: async (id: string): Promise<Blob> => {
  const response = await api.get(`/iso/exports/snapshots/${id}`, {
    responseType: 'blob',
  });
  return response.data;
},
```

**Step 3: Create useIsoExport hook**

`frontend/src/hooks/useIsoExport.ts`:

```typescript
import { useState } from 'react';
import { isoApi } from '../services/api';
import { downloadBlob } from '../utils/file';

interface UseIsoExportReturn {
  exportSnapshots: (from: string, to: string) => Promise<void>;
  exportSnapshot: (id: string, capturedAt: string) => Promise<void>;
  isExporting: boolean;
  error: string | null;
}

export function useIsoExport(): UseIsoExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportSnapshots = async (from: string, to: string): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const blob = await isoApi.exportSnapshots(from, to);
      downloadBlob(blob, `iso_access_review_${from}_${to}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportSnapshot = async (
    id: string,
    capturedAt: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const blob = await isoApi.exportSnapshot(id);
      const dateStr = capturedAt.slice(0, 10);
      downloadBlob(blob, `iso_access_review_${dateStr}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return { exportSnapshots, exportSnapshot, isExporting, error };
}
```

**Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(iso): add frontend export API, hook, and shared downloadBlob util"
```

---

### Task 6: Add export UI to snapshots list and detail pages

**Files:**
- Modify: `frontend/src/pages/ISOSnapshots.tsx`
- Modify: `frontend/src/pages/ISOSnapshotDetail.tsx`

**Step 1: Add export to ISOSnapshots.tsx**

Add import:
```typescript
import { useIsoExport } from '@/hooks/useIsoExport';
import { Download } from 'lucide-react';
```

Add state and hook inside the component:
```typescript
const { exportSnapshots, isExporting } = useIsoExport();
const currentYear = new Date().getFullYear();
const [exportYear, setExportYear] = useState(currentYear);
```

Add export button group in the header area (next to the "Capture Snapshot" button):
```tsx
<div className="flex items-center gap-2">
  <Select
    value={String(exportYear)}
    onValueChange={(v) => setExportYear(Number(v))}
  >
    <SelectTrigger className="w-28">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
        <SelectItem key={y} value={String(y)}>{y}</SelectItem>
      ))}
    </SelectContent>
  </Select>
  <Button
    variant="outline"
    onClick={() => exportSnapshots(`${exportYear}-01-01`, `${exportYear}-12-31`)}
    disabled={isExporting}
    className="gap-2"
  >
    <Download className="h-4 w-4" />
    {isExporting ? 'Exporting...' : 'Export Year'}
  </Button>
</div>
```

Add necessary Select imports from `@/components/ui/select`.

**Step 2: Add export button to ISOSnapshotDetail.tsx**

Add import:
```typescript
import { useIsoExport } from '@/hooks/useIsoExport';
import { Download } from 'lucide-react';
```

Add hook inside the component:
```typescript
const { exportSnapshot, isExporting } = useIsoExport();
```

Add button in the header area (next to the provider badge):
```tsx
<Button
  variant="outline"
  size="sm"
  onClick={() => exportSnapshot(id!, snapshot.captured_at)}
  disabled={isExporting}
  className="gap-2"
>
  <Download className="h-4 w-4" />
  {isExporting ? 'Exporting...' : 'Export'}
</Button>
```

**Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

**Step 4: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: All pass (existing tests shouldn't break — new buttons are additive).

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(iso): add export buttons to snapshots list and detail pages"
```

---

### Task 7: Add frontend tests for export UI

**Files:**
- Modify: `frontend/src/pages/__tests__/ISOSnapshots.test.tsx`
- Modify: `frontend/src/pages/__tests__/ISOSnapshotDetail.test.tsx`

**Step 1: Update ISOSnapshots test**

Add mock for `useIsoExport`:
```typescript
const mockExportSnapshots = vi.fn();
const mockUseIsoExport = vi.fn();

vi.mock('../../hooks/useIsoExport', () => ({
  useIsoExport: () => mockUseIsoExport(),
}));
```

In `beforeEach`:
```typescript
mockUseIsoExport.mockReturnValue({
  exportSnapshots: mockExportSnapshots,
  exportSnapshot: vi.fn(),
  isExporting: false,
  error: null,
});
```

Add test:
```typescript
it('renders export year button', () => {
  renderWithProviders(<ISOSnapshots />);
  expect(screen.getByRole('button', { name: /export year/i })).toBeInTheDocument();
});
```

**Step 2: Update ISOSnapshotDetail test**

Add mock for `useIsoExport`:
```typescript
const mockExportSnapshot = vi.fn();
const mockUseIsoExport = vi.fn();

vi.mock('../../hooks/useIsoExport', () => ({
  useIsoExport: () => mockUseIsoExport(),
}));
```

In `beforeEach`:
```typescript
mockUseIsoExport.mockReturnValue({
  exportSnapshots: vi.fn(),
  exportSnapshot: mockExportSnapshot,
  isExporting: false,
  error: null,
});
```

Add test:
```typescript
it('renders export button on detail page', () => {
  renderWithProviders(<ISOSnapshotDetail />);
  expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
});
```

**Step 3: Run all frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: All pass.

**Step 4: Commit**

```bash
git add -A && git commit -m "test(iso): add frontend tests for export buttons"
```

---

## Phase 4: Final Verification

### Task 8: Full verification

**Step 1: Backend tests**

```bash
cd backend && pytest -v
```

Expected: All ~830+ tests pass.

**Step 2: Frontend TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: All ~294+ tests pass.

**Step 4: Frontend lint + build**

```bash
cd frontend && npm run lint && npm run build
```

**Step 5: Backend lint**

```bash
cd backend && ruff check app/ && black --check app/
```
