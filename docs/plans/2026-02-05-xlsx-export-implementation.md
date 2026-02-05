# XLSX Export Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add XLSX export endpoints for project detail and global dashboard, with ISO audit-ready formatting (KPI descriptions, formulas, traffic light colors, methodology sheet).

**Architecture:** A backend `ExportService` generates XLSX files in memory using `openpyxl`. Two GET endpoints return `StreamingResponse` with the file. Frontend adds date range pickers and export buttons to `SnapshotManager` and `GlobalDashboard`.

**Tech Stack:** openpyxl (backend), existing FastAPI/SQLAlchemy/React Query stack.

**Design doc:** `docs/plans/2026-02-05-xlsx-export-design.md`

---

### Task 1: Add openpyxl dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add dependency**

Add to `backend/requirements.txt` after the Configuration section:

```
# Export
openpyxl>=3.1.0,<4.0.0
```

**Step 2: Install**

Run: `cd backend && pip install openpyxl`

**Step 3: Verify**

Run: `python -c "import openpyxl; print(openpyxl.__version__)"`
Expected: Version number printed.

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add openpyxl dependency for XLSX export"
```

---

### Task 2: Create export metric definitions

This is the static catalog of KPIs with descriptions and formulas that populate the Metrics sheet rows. It maps indicator/dimension names to human-readable info for auditors.

**Files:**
- Create: `backend/app/services/export_definitions.py`
- Test: `backend/tests/test_export_definitions.py`

**Step 1: Write the test**

```python
"""Tests for export metric definitions."""

from app.services.export_definitions import (
    DIMENSION_DEFINITIONS,
    INDICATOR_DEFINITIONS,
    get_metric_rows,
)


class TestExportDefinitions:
    def test_all_eight_dimensions_defined(self):
        dims = [d["key"] for d in DIMENSION_DEFINITIONS]
        expected = [
            "p_time", "p_cost", "p_quality", "p_value",
            "p_satisfaction", "p_flow", "p_engineering", "p_risk",
        ]
        assert dims == expected

    def test_dimension_has_required_fields(self):
        for dim in DIMENSION_DEFINITIONS:
            assert "key" in dim
            assert "name" in dim
            assert "description" in dim
            assert "formula" in dim
            assert "indicators" in dim

    def test_indicator_has_required_fields(self):
        for key, ind in INDICATOR_DEFINITIONS.items():
            assert "name" in ind, f"Missing name for {key}"
            assert "description" in ind, f"Missing description for {key}"
            assert "formula" in ind, f"Missing formula for {key}"

    def test_get_metric_rows_returns_hierarchical_list(self):
        rows = get_metric_rows()
        assert len(rows) > 0
        assert rows[0]["level"] == 0
        assert rows[0]["key"] == "final_score"
        # Dimensions should be level 1
        dim_rows = [r for r in rows if r["level"] == 1]
        assert len(dim_rows) == 8
        # Indicators should be level 2
        ind_rows = [r for r in rows if r["level"] == 2]
        assert len(ind_rows) > 0

    def test_each_dimension_has_at_least_one_indicator(self):
        rows = get_metric_rows()
        current_dim = None
        dim_has_indicators = {}
        for row in rows:
            if row["level"] == 1:
                current_dim = row["key"]
                dim_has_indicators[current_dim] = False
            elif row["level"] == 2 and current_dim:
                dim_has_indicators[current_dim] = True
        for dim, has in dim_has_indicators.items():
            assert has, f"Dimension {dim} has no indicators"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_export_definitions.py -v`
Expected: FAIL — module not found.

**Step 3: Write implementation**

Create `backend/app/services/export_definitions.py`:

```python
"""Metric definitions for XLSX export — names, descriptions, formulas for ISO audits."""


INDICATOR_DEFINITIONS: dict[str, dict[str, str]] = {
    # P_time
    "spi": {
        "name": "Schedule Performance Index",
        "description": "Ratio of earned value to planned value. Measures schedule efficiency.",
        "formula": "EV / PV (where EV = budget_total * percent_completed, PV = budget_total * percent_planned)",
    },
    "on_time_milestones": {
        "name": "On-Time Milestones",
        "description": "Weighted ratio of milestones delivered on time, with grace period.",
        "formula": "Sum(weight * on_time) / Sum(weight) for each milestone",
    },
    # P_cost
    "cpi": {
        "name": "Cost Performance Index",
        "description": "Ratio of earned value to actual cost. Measures cost efficiency.",
        "formula": "EV / AC (where EV = budget_total * percent_completed, AC = cost_to_date)",
    },
    "budget_variance": {
        "name": "Budget Variance",
        "description": "Percentage of budget overrun.",
        "formula": "(cost_to_date - planned_cost) / budget_total * 100",
    },
    # P_quality
    "defect_density": {
        "name": "Defect Density",
        "description": "Number of bugs per 100 completed tasks.",
        "formula": "(bugs_total / tasks_completed) * 100",
    },
    "escaped_rate": {
        "name": "Escaped Defect Rate",
        "description": "Escaped defects per 100 completed tasks.",
        "formula": "(escaped_defects / tasks_completed) * 100",
    },
    "mttr_hours": {
        "name": "Mean Time to Recovery",
        "description": "Average hours to resolve incidents.",
        "formula": "mttr_hours (from Jira resolution times)",
    },
    "governance_compliance": {
        "name": "Governance Compliance",
        "description": "Compliance based on number of governance exceptions.",
        "formula": "max(0, 1 - (exceptions / target)). Zero exceptions = 1.0",
    },
    "story_review_ratio": {
        "name": "Story Review Ratio",
        "description": "Ratio of stories that had a reviewer assigned.",
        "formula": "stories_with_reviewer / total_stories",
    },
    "pr_review_ratio": {
        "name": "PR Review Ratio",
        "description": "Ratio of PRs merged with at least one review.",
        "formula": "(total_merged_prs - prs_without_review) / total_merged_prs",
    },
    "change_failure_rate": {
        "name": "Change Failure Rate",
        "description": "Percentage of releases that caused failures (DORA metric).",
        "formula": "failed_releases / total_releases * 100",
    },
    "post_contract_tasks": {
        "name": "Post-Contract Tasks",
        "description": "Tasks created more than 30 days after contract end date.",
        "formula": "Count of tasks created > 30 days after project end_date",
    },
    # P_value
    "okr_impact": {
        "name": "Strategic Impact",
        "description": "Assessment of project's strategic value to the organization.",
        "formula": "LOW=0.25, MEDIUM=0.55, HIGH=0.80, TRANSFORMATIONAL=1.0",
    },
    # P_satisfaction
    "pm_satisfaction": {
        "name": "PM Satisfaction",
        "description": "Project manager's estimation of client satisfaction.",
        "formula": "Weighted score from delivery complaints, design complaints, overall estimation",
    },
    "client_satisfaction": {
        "name": "Client Survey Score",
        "description": "Weighted average of 8 client survey questions (1-5 scale).",
        "formula": "Sum(question_score * question_weight) / Sum(question_weight), normalized to 0-1",
    },
    # P_flow
    "lead_time_days": {
        "name": "Lead Time",
        "description": "Average days from issue creation to completion.",
        "formula": "Average (done_date - created_date) for completed issues",
    },
    "commitment_reliability": {
        "name": "Commitment Reliability",
        "description": "Ratio of issues completed within a single sprint.",
        "formula": "single_sprint_issues / committed_issues",
    },
    "pr_size_median": {
        "name": "PR Size (Median)",
        "description": "Median number of changed lines per pull request.",
        "formula": "Median(additions + deletions) across merged PRs",
    },
    "review_turnaround_hours": {
        "name": "Review Turnaround",
        "description": "Median hours from PR creation to first review.",
        "formula": "Median(first_review_time - pr_created_time) for reviewed PRs",
    },
    "deployment_frequency": {
        "name": "Deployment Frequency",
        "description": "Average releases per day over 90-day window (DORA metric).",
        "formula": "release_count_90d / 90",
    },
    # P_engineering
    "test_maturity": {
        "name": "Test Maturity",
        "description": "Weighted score across 5 testing dimensions (1-5 scale each).",
        "formula": "Sum(dimension_score * dimension_weight) / (5 * Sum(weights)), normalized to 0-1",
    },
    "arch_checklist": {
        "name": "Architecture Checklist",
        "description": "Completion ratio of architecture best practices.",
        "formula": "completed_items / total_items (docs, IaC, ADRs, diagrams)",
    },
    # P_risk
    "prs_without_review": {
        "name": "PRs Without Review",
        "description": "Count of pull requests merged without any review.",
        "formula": "Count of PRs with 0 reviews at merge time",
    },
    "high_vulns": {
        "name": "High Severity Vulnerabilities",
        "description": "High/critical vulnerabilities unresolved for >30 days.",
        "formula": "Count from Dependabot alerts (high + critical, open > 30 days)",
    },
}


DIMENSION_DEFINITIONS: list[dict] = [
    {
        "key": "p_time",
        "name": "P_time — Schedule",
        "description": "Schedule adherence measured through earned value and milestone delivery.",
        "formula": "w_spi * normalize(SPI, ideal) + w_milestones * normalize(on_time_milestones, target)",
        "indicators": ["spi", "on_time_milestones"],
    },
    {
        "key": "p_cost",
        "name": "P_cost — Budget",
        "description": "Budget adherence measured through cost performance index and variance.",
        "formula": "w_cpi * normalize(CPI, ideal) + w_variance * normalize(budget_variance, target)",
        "indicators": ["cpi", "budget_variance"],
    },
    {
        "key": "p_quality",
        "name": "P_quality — Quality",
        "description": "Software quality across defects, governance, reviews, and failure rates. Capped at 60 if Sev1 incident.",
        "formula": "weighted_avg(defect_density, escaped_rate, mttr, story_review, governance, pr_review, change_failure_rate, post_contract_tasks). Sev1 cap applied.",
        "indicators": [
            "defect_density", "escaped_rate", "mttr_hours",
            "governance_compliance", "story_review_ratio", "pr_review_ratio",
            "change_failure_rate", "post_contract_tasks",
        ],
    },
    {
        "key": "p_value",
        "name": "P_value — Strategic Value",
        "description": "Strategic impact assessment of the project.",
        "formula": "w_okr * normalize(okr_impact)",
        "indicators": ["okr_impact"],
    },
    {
        "key": "p_satisfaction",
        "name": "P_satisfaction — Satisfaction",
        "description": "Stakeholder satisfaction from PM estimation and client survey.",
        "formula": "w_client * normalize(client_survey) + w_pm * normalize(pm_estimation)",
        "indicators": ["pm_satisfaction", "client_satisfaction"],
    },
    {
        "key": "p_flow",
        "name": "P_flow — Flow & Predictability",
        "description": "Development flow efficiency and predictability.",
        "formula": "weighted_avg(lead_time, commitment_reliability, pr_size, review_turnaround, deployment_frequency)",
        "indicators": [
            "lead_time_days", "commitment_reliability", "pr_size_median",
            "review_turnaround_hours", "deployment_frequency",
        ],
    },
    {
        "key": "p_engineering",
        "name": "P_engineering — Engineering Maturity",
        "description": "Engineering practices maturity across testing, reviews, and architecture.",
        "formula": "weighted_avg(test_maturity, pr_review, architecture)",
        "indicators": ["test_maturity", "pr_review_ratio", "arch_checklist"],
    },
    {
        "key": "p_risk",
        "name": "P_risk — Risk Posture",
        "description": "Risk exposure from unreviewed code and security vulnerabilities.",
        "formula": "weighted_avg(pr_no_review_penalty, high_vulns_penalty)",
        "indicators": ["prs_without_review", "high_vulns"],
    },
]


def get_metric_rows() -> list[dict]:
    """Build hierarchical list of metric rows for the XLSX Metrics sheet.

    Returns list of dicts with keys: level, key, name, description, formula.
    Level 0 = final score, level 1 = dimension, level 2 = indicator.
    """
    rows: list[dict] = []

    rows.append({
        "level": 0,
        "key": "final_score",
        "name": "FINAL SCORE",
        "description": "Weighted aggregate of all 8 dimension scores.",
        "formula": "Sum(dimension_score * global_weight) for active dimensions",
    })

    for dim in DIMENSION_DEFINITIONS:
        rows.append({
            "level": 1,
            "key": dim["key"],
            "name": dim["name"],
            "description": dim["description"],
            "formula": dim["formula"],
        })
        for ind_key in dim["indicators"]:
            ind = INDICATOR_DEFINITIONS[ind_key]
            rows.append({
                "level": 2,
                "key": ind_key,
                "name": ind["name"],
                "description": ind["description"],
                "formula": ind["formula"],
            })

    return rows
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_export_definitions.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/app/services/export_definitions.py backend/tests/test_export_definitions.py
git commit -m "feat: add export metric definitions for XLSX audit sheets"
```

---

### Task 3: Create export helpers (styling and methodology sheet)

Shared formatting utilities: header styles, traffic light fills, column widths, methodology sheet generation.

**Files:**
- Create: `backend/app/services/export_helpers.py`
- Test: `backend/tests/test_export_helpers.py`

**Step 1: Write the test**

```python
"""Tests for export XLSX helpers."""

import pytest
from openpyxl import Workbook
from openpyxl.styles import PatternFill

from app.services.export_helpers import (
    apply_header_style,
    apply_traffic_light,
    create_methodology_sheet,
    format_month_header,
    set_column_widths,
)
from tests.conftest import load_config_from_csv
from app.config import ScoringConfig


@pytest.fixture
def wb():
    return Workbook()


@pytest.fixture
def config():
    return ScoringConfig(load_config_from_csv())


class TestTrafficLight:
    def test_green_when_above_target(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=90)
        apply_traffic_light(cell, 90, 80)
        assert cell.fill.start_color.rgb == "FF4CAF50"  # Green

    def test_yellow_when_near_target(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=70)
        apply_traffic_light(cell, 70, 80)
        assert cell.fill.start_color.rgb == "FFFFC107"  # Yellow

    def test_red_when_below_threshold(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=50)
        apply_traffic_light(cell, 50, 80)
        assert cell.fill.start_color.rgb == "FFF44336"  # Red

    def test_no_fill_when_value_is_none(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=None)
        apply_traffic_light(cell, None, 80)
        assert cell.fill == PatternFill()

    def test_no_fill_when_target_is_none(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=85)
        apply_traffic_light(cell, 85, None)
        assert cell.fill == PatternFill()


class TestHeaderStyle:
    def test_applies_bold_and_fill(self, wb):
        ws = wb.active
        ws.append(["Col1", "Col2", "Col3"])
        apply_header_style(ws, row=1)
        for col in range(1, 4):
            cell = ws.cell(row=1, column=col)
            assert cell.font.bold is True


class TestFormatMonthHeader:
    def test_formats_correctly(self):
        assert format_month_header(2025, 1) == "Jan 2025"
        assert format_month_header(2025, 12) == "Dec 2025"


class TestMethodologySheet:
    def test_creates_sheet_with_content(self, wb, config):
        create_methodology_sheet(wb, config)
        assert "Methodology" in wb.sheetnames
        ws = wb["Methodology"]
        assert ws.cell(row=1, column=1).value is not None


class TestColumnWidths:
    def test_sets_widths(self, wb):
        ws = wb.active
        ws.append(["Name", "Description", "Formula", "Target", "Jan 2025"])
        widths = {"A": 30, "B": 50, "C": 40, "D": 12}
        set_column_widths(ws, widths)
        assert ws.column_dimensions["A"].width == 30
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_export_helpers.py -v`
Expected: FAIL — module not found.

**Step 3: Write implementation**

Create `backend/app/services/export_helpers.py`:

```python
"""Shared XLSX formatting helpers for export service."""

import calendar

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from app.config import ScoringConfig
from app.services.export_definitions import DIMENSION_DEFINITIONS, INDICATOR_DEFINITIONS

# Traffic light colors
GREEN_FILL = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFC107", end_color="FFC107", fill_type="solid")
RED_FILL = PatternFill(start_color="F44336", end_color="F44336", fill_type="solid")

# Header style
HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Dimension row style
DIM_FILL = PatternFill(start_color="E5E7EB", end_color="E5E7EB", fill_type="solid")
DIM_FONT = Font(bold=True, size=11)

# Score row style (level 0)
SCORE_FONT = Font(bold=True, size=12)
SCORE_FILL = PatternFill(start_color="D1D5DB", end_color="D1D5DB", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)

# Yellow threshold: value >= 80% of target
YELLOW_THRESHOLD = 0.8


def apply_traffic_light(
    cell,
    value: float | int | None,
    target: float | int | None,
) -> None:
    """Apply green/yellow/red fill based on value vs target."""
    if value is None or target is None:
        return

    if value >= target:
        cell.fill = GREEN_FILL
    elif value >= target * YELLOW_THRESHOLD:
        cell.fill = YELLOW_FILL
    else:
        cell.fill = RED_FILL


def apply_header_style(ws: Worksheet, row: int = 1) -> None:
    """Apply dark header style to a row."""
    for cell in ws[row]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def apply_row_style(ws: Worksheet, row: int, level: int) -> None:
    """Apply style based on hierarchy level."""
    for cell in ws[row]:
        cell.border = THIN_BORDER
        if level == 0:
            cell.font = SCORE_FONT
            cell.fill = SCORE_FILL
        elif level == 1:
            cell.font = DIM_FONT
            cell.fill = DIM_FILL


def format_month_header(year: int, month: int) -> str:
    """Format year/month as 'Jan 2025'."""
    return f"{calendar.month_abbr[month]} {year}"


def set_column_widths(ws: Worksheet, widths: dict[str, int]) -> None:
    """Set column widths from a dict of column letter -> width."""
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def freeze_panes(ws: Worksheet, row: int, col: int) -> None:
    """Freeze rows above and columns to the left of the given cell."""
    ws.freeze_panes = ws.cell(row=row, column=col)


def create_methodology_sheet(wb: Workbook, config: ScoringConfig) -> Worksheet:
    """Create the Methodology sheet with scoring model explanation and current config."""
    ws = wb.create_sheet("Methodology")

    # Title
    ws.append(["Scoring Methodology"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([])

    # Scoring model overview
    ws.append(["Scoring Model"])
    ws.cell(row=3, column=1).font = Font(bold=True, size=12)
    ws.append(["Raw Metrics", "->", "Normalized Indicators (0-1)", "->", "Weighted Scores (0-100)"])
    ws.append(["Collectors fetch data from Jira and GitHub. Manual inputs supplement automated data."])
    ws.append(["Indicators are normalized to a 0-1 scale. Scores are weighted averages scaled to 0-100."])
    ws.append([])

    # Traffic light legend
    ws.append(["Traffic Light Legend"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    row = ws.max_row + 1
    ws.cell(row=row, column=1, value="Green").fill = GREEN_FILL
    ws.cell(row=row, column=2, value="Value >= Target")
    row += 1
    ws.cell(row=row, column=1, value="Yellow").fill = YELLOW_FILL
    ws.cell(row=row, column=2, value="Value >= 80% of Target")
    row += 1
    ws.cell(row=row, column=1, value="Red").fill = RED_FILL
    ws.cell(row=row, column=2, value="Value < 80% of Target")
    ws.append([])

    # Snapshot types
    ws.append(["Snapshot Types"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    ws.append(["Cumulative", "Project-to-date metrics from start_date to period end"])
    ws.append(["Punctual", "Single month metrics for that period only"])
    ws.append([])

    # Global weights
    ws.append(["Global Dimension Weights"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    ws.append(["Dimension", "Weight"])
    dims = ["time", "cost", "quality", "value", "satisfaction", "flow", "engineering", "risk"]
    for dim in dims:
        weight = config.get_weight("global", dim)
        ws.append([f"P_{dim}", f"{weight:.0%}"])
    ws.append([])

    # KPI reference table
    ws.append(["KPI Reference"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    headers = ["Dimension", "Indicator", "Description", "Formula", "Target", "Weight"]
    ws.append(headers)
    header_row = ws.max_row
    apply_header_style(ws, header_row)

    for dim_def in DIMENSION_DEFINITIONS:
        dim_key = dim_def["key"].replace("p_", "")
        for ind_key in dim_def["indicators"]:
            ind = INDICATOR_DEFINITIONS[ind_key]
            target = _safe_get_target(config, ind_key)
            weight = _safe_get_weight(config, dim_key, ind_key)
            ws.append([
                dim_def["name"],
                ind["name"],
                ind["description"],
                ind["formula"],
                target,
                weight,
            ])

    # Column widths
    set_column_widths(ws, {"A": 25, "B": 28, "C": 50, "D": 60, "E": 12, "F": 12})

    return ws


def _safe_get_target(config: ScoringConfig, indicator_key: str) -> str:
    """Get target value as string, return '-' if not configured."""
    try:
        val = config.get_target(indicator_key)
        if val == 0.0:
            return "-"
        return str(val)
    except (KeyError, ValueError):
        return "-"


def _safe_get_weight(config: ScoringConfig, dim_key: str, ind_key: str) -> str:
    """Get weight value as string, return '-' if not configured."""
    # Map indicator keys to weight names used in ScoringConfig
    weight_map = {
        "spi": ("time", "spi"),
        "on_time_milestones": ("time", "milestones"),
        "cpi": ("cost", "cpi"),
        "budget_variance": ("cost", "variance"),
        "defect_density": ("quality", "defect_density"),
        "escaped_rate": ("quality", "escaped_rate"),
        "mttr_hours": ("quality", "mttr"),
        "governance_compliance": ("quality", "governance"),
        "story_review_ratio": ("quality", "story_review"),
        "pr_review_ratio": ("quality", "pr_review"),
        "change_failure_rate": ("quality", "change_failure_rate"),
        "post_contract_tasks": ("quality", "post_contract_tasks"),
        "okr_impact": ("value", "okr_impact"),
        "pm_satisfaction": ("satisfaction", "pm_estimation"),
        "client_satisfaction": ("satisfaction", "client_survey"),
        "lead_time_days": ("flow", "lead_time"),
        "commitment_reliability": ("flow", "commitment_reliability"),
        "pr_size_median": ("flow", "pr_size"),
        "review_turnaround_hours": ("flow", "review_turnaround"),
        "deployment_frequency": ("flow", "deployment_frequency"),
        "test_maturity": ("engineering", "test_maturity"),
        "arch_checklist": ("engineering", "architecture"),
        "prs_without_review": ("risk", "pr_no_review"),
        "high_vulns": ("risk", "high_vulns"),
    }
    mapping = weight_map.get(ind_key)
    if not mapping:
        return "-"
    try:
        val = config.get_weight(mapping[0], mapping[1])
        return f"{val:.0%}"
    except (KeyError, ValueError):
        return "-"
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_export_helpers.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/app/services/export_helpers.py backend/tests/test_export_helpers.py
git commit -m "feat: add XLSX export helpers (styling, traffic light, methodology)"
```

---

### Task 4: Create ExportService — project detail export

The core service that builds the XLSX workbook for a single project.

**Files:**
- Create: `backend/app/services/export_service.py`
- Test: `backend/tests/test_export_service.py`

**Step 1: Write the test**

```python
"""Tests for ExportService."""

import pytest
import pytest_asyncio
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsDB
from app.models.project import ProjectDB
from app.services.export_service import ExportService


@pytest_asyncio.fixture
async def project_with_3_months(
    db_session: AsyncSession, scoring_config: ScoringConfig
) -> ProjectDB:
    """Create a project with 3 months of metrics."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Export Test Project",
        jira_project_key="EXP",
        github_repo="test/export",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="in_progress",
    )
    db_session.add(project)

    for month in range(1, 4):
        metrics = MetricsDB(
            project_id=str(project.id),
            period_start=date(2025, month, 1),
            period_end=date(2025, month, 28),
            period_year=2025,
            period_month=month,
            snapshot_type="cumulative",
            budget_total=Decimal("100000"),
            cost_to_date=Decimal(str(40000 + month * 5000)),
            percent_completed=Decimal(str(0.1 * month)),
            percent_planned=Decimal(str(0.1 * month)),
            bugs_total=5 + month,
            tasks_completed=100,
            governance_exceptions=1,
            sev1_incident=False,
            total_merged_prs=50,
            prs_without_review=2,
        )
        db_session.add(metrics)

    await db_session.commit()
    await db_session.refresh(project)
    return project


class TestExportServiceProjectDetail:
    @pytest.mark.asyncio
    async def test_generates_valid_xlsx(
        self, db_session, scoring_config, project_with_3_months
    ):
        project = project_with_3_months
        service = ExportService(scoring_config)
        output = await service.export_project_detail(
            db=db_session,
            project_id=str(project.id),
            start_year=2025,
            start_month=1,
            end_year=2025,
            end_month=3,
            snapshot_type="cumulative",
        )
        assert isinstance(output, BytesIO)
        wb = load_workbook(output)
        assert "Summary" in wb.sheetnames
        assert "Metrics" in wb.sheetnames
        assert "Methodology" in wb.sheetnames

    @pytest.mark.asyncio
    async def test_summary_sheet_has_project_info(
        self, db_session, scoring_config, project_with_3_months
    ):
        project = project_with_3_months
        service = ExportService(scoring_config)
        output = await service.export_project_detail(
            db=db_session,
            project_id=str(project.id),
            start_year=2025,
            start_month=1,
            end_year=2025,
            end_month=3,
            snapshot_type="cumulative",
        )
        wb = load_workbook(output)
        ws = wb["Summary"]
        # Project name should appear in the sheet
        values = [ws.cell(row=r, column=2).value for r in range(1, 10)]
        assert "Export Test Project" in values

    @pytest.mark.asyncio
    async def test_metrics_sheet_has_month_columns(
        self, db_session, scoring_config, project_with_3_months
    ):
        project = project_with_3_months
        service = ExportService(scoring_config)
        output = await service.export_project_detail(
            db=db_session,
            project_id=str(project.id),
            start_year=2025,
            start_month=1,
            end_year=2025,
            end_month=3,
            snapshot_type="cumulative",
        )
        wb = load_workbook(output)
        ws = wb["Metrics"]
        # Header row should contain month headers starting from column 5 (E)
        headers = [ws.cell(row=1, column=c).value for c in range(5, 8)]
        assert "Jan 2025" in headers
        assert "Feb 2025" in headers
        assert "Mar 2025" in headers

    @pytest.mark.asyncio
    async def test_metrics_sheet_has_hierarchical_rows(
        self, db_session, scoring_config, project_with_3_months
    ):
        project = project_with_3_months
        service = ExportService(scoring_config)
        output = await service.export_project_detail(
            db=db_session,
            project_id=str(project.id),
            start_year=2025,
            start_month=1,
            end_year=2025,
            end_month=3,
            snapshot_type="cumulative",
        )
        wb = load_workbook(output)
        ws = wb["Metrics"]
        # First data row (row 2) should be FINAL SCORE
        assert ws.cell(row=2, column=1).value == "FINAL SCORE"

    @pytest.mark.asyncio
    async def test_empty_range_returns_xlsx_with_no_data_columns(
        self, db_session, scoring_config, project_with_3_months
    ):
        project = project_with_3_months
        service = ExportService(scoring_config)
        output = await service.export_project_detail(
            db=db_session,
            project_id=str(project.id),
            start_year=2024,
            start_month=1,
            end_year=2024,
            end_month=3,
            snapshot_type="cumulative",
        )
        assert isinstance(output, BytesIO)
        wb = load_workbook(output)
        assert "Metrics" in wb.sheetnames
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_export_service.py -v`
Expected: FAIL — module not found.

**Step 3: Write implementation**

Create `backend/app/services/export_service.py`:

```python
"""XLSX export service for project scorecard data."""

from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.models.project import ProjectDB
from app.services.export_definitions import get_metric_rows
from app.services.export_helpers import (
    apply_header_style,
    apply_row_style,
    apply_traffic_light,
    create_methodology_sheet,
    format_month_header,
    freeze_panes,
    set_column_widths,
    THIN_BORDER,
)
from app.services.score_computation import ScoreComputationService


class ExportService:
    """Generates XLSX exports for scorecard data."""

    def __init__(self, config: ScoringConfig):
        self.config = config
        self.score_service = ScoreComputationService(config)

    async def export_project_detail(
        self,
        db: AsyncSession,
        project_id: str,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        snapshot_type: str = "cumulative",
    ) -> BytesIO:
        """Generate project detail XLSX with Summary, Metrics, and Methodology sheets."""
        project = await self._get_project(db, project_id)
        periods = self._generate_periods(start_year, start_month, end_year, end_month)
        metrics_by_period = await self._get_metrics_by_period(
            db, project_id, periods, snapshot_type
        )
        scores_by_period = self._compute_scores(metrics_by_period)

        wb = Workbook()

        self._build_summary_sheet(wb, project, periods, scores_by_period, snapshot_type)
        self._build_metrics_sheet(wb, periods, metrics_by_period, scores_by_period)
        create_methodology_sheet(wb, self.config)

        # Remove default sheet if still there
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        return self._save_to_bytes(wb)

    async def export_global_dashboard(
        self,
        db: AsyncSession,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        snapshot_type: str = "cumulative",
    ) -> BytesIO:
        """Generate global dashboard XLSX with Overview, Dimensions, and Methodology sheets."""
        projects = await self._get_all_projects(db)
        periods = self._generate_periods(start_year, start_month, end_year, end_month)

        # Collect data per project
        project_data: list[dict] = []
        for project in projects:
            metrics_by_period = await self._get_metrics_by_period(
                db, str(project.id), periods, snapshot_type
            )
            scores_by_period = self._compute_scores(metrics_by_period)
            project_data.append({
                "project": project,
                "scores": scores_by_period,
            })

        wb = Workbook()

        self._build_overview_sheet(wb, project_data, periods)
        self._build_dimensions_sheet(wb, project_data, periods)
        create_methodology_sheet(wb, self.config)

        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        return self._save_to_bytes(wb)

    # --- Data fetching ---

    async def _get_project(self, db: AsyncSession, project_id: str) -> ProjectDB:
        result = await db.execute(
            select(ProjectDB).where(ProjectDB.id == UUID(project_id))
        )
        return result.scalar_one()

    async def _get_all_projects(self, db: AsyncSession) -> list[ProjectDB]:
        result = await db.execute(select(ProjectDB).order_by(ProjectDB.name))
        return list(result.scalars().all())

    async def _get_metrics_by_period(
        self,
        db: AsyncSession,
        project_id: str,
        periods: list[tuple[int, int]],
        snapshot_type: str,
    ) -> dict[tuple[int, int], MetricsDB | None]:
        """Fetch metrics for each period, returns dict of (year, month) -> MetricsDB."""
        result: dict[tuple[int, int], MetricsDB | None] = {}
        for year, month in periods:
            query = (
                select(MetricsDB)
                .where(MetricsDB.project_id == UUID(project_id))
                .where(MetricsDB.period_year == year)
                .where(MetricsDB.period_month == month)
                .where(MetricsDB.snapshot_type == snapshot_type)
                .order_by(MetricsDB.created_at.desc())
                .limit(1)
            )
            res = await db.execute(query)
            result[(year, month)] = res.scalar_one_or_none()
        return result

    # --- Score computation ---

    def _compute_scores(
        self,
        metrics_by_period: dict[tuple[int, int], MetricsDB | None],
    ) -> dict[tuple[int, int], dict | None]:
        """Compute scores for each period, returns dict of (year, month) -> score data."""
        result: dict[tuple[int, int], dict | None] = {}
        for period, metrics_db in metrics_by_period.items():
            if metrics_db is None:
                result[period] = None
                continue
            metrics = MetricsCreate.from_db(metrics_db)
            indicators, scores = self.score_service.compute(
                metrics, sev1_incident=metrics_db.sev1_incident
            )
            result[period] = {
                "indicators": indicators,
                "scores": scores,
            }
        return result

    # --- Sheet builders ---

    def _build_summary_sheet(
        self,
        wb: Workbook,
        project: ProjectDB,
        periods: list[tuple[int, int]],
        scores_by_period: dict,
        snapshot_type: str,
    ) -> None:
        ws = wb.active
        ws.title = "Summary"

        # Project info
        info = [
            ("Project", project.name),
            ("Jira Key", project.jira_project_key or "-"),
            ("GitHub Repo", project.github_repo or "-"),
            ("Status", project.status),
            ("Start Date", str(project.start_date) if project.start_date else "-"),
            ("End Date", str(project.end_date) if project.end_date else "-"),
            ("Snapshot Type", snapshot_type),
        ]
        for label, value in info:
            ws.append([label, value])

        ws.append([])

        # Final score per month
        header = ["Final Score"] + [format_month_header(y, m) for y, m in periods]
        ws.append(header)
        apply_header_style(ws, ws.max_row)

        values = ["Score"]
        for period in periods:
            data = scores_by_period.get(period)
            values.append(data["scores"].score if data else None)
        ws.append(values)

        set_column_widths(ws, {"A": 20, "B": 30})

    def _build_metrics_sheet(
        self,
        wb: Workbook,
        periods: list[tuple[int, int]],
        metrics_by_period: dict,
        scores_by_period: dict,
    ) -> None:
        ws = wb.create_sheet("Metrics")
        metric_rows = get_metric_rows()

        # Header row
        header = ["Name", "Description", "Formula", "Target"]
        for year, month in periods:
            header.append(format_month_header(year, month))
        ws.append(header)
        apply_header_style(ws, 1)

        # Data rows
        for metric_row in metric_rows:
            level = metric_row["level"]
            indent = "  " * level
            target = self._get_target_for_metric(metric_row["key"], level)

            row_data = [
                f"{indent}{metric_row['name']}",
                metric_row["description"],
                metric_row["formula"],
                target if target else "-",
            ]

            for period in periods:
                value = self._extract_value(
                    metric_row["key"], level, scores_by_period.get(period)
                )
                row_data.append(value)

            ws.append(row_data)
            current_row = ws.max_row
            apply_row_style(ws, current_row, level)

            # Traffic light on value cells
            target_num = self._parse_target(target)
            for col_idx, period in enumerate(periods, start=5):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                if level <= 1 and target_num is not None:
                    apply_traffic_light(cell, cell.value, target_num)

        # Column widths
        widths = {"A": 35, "B": 50, "C": 45, "D": 12}
        for i, _ in enumerate(periods):
            widths[get_column_letter(5 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 2, 5)

    def _build_overview_sheet(
        self,
        wb: Workbook,
        project_data: list[dict],
        periods: list[tuple[int, int]],
    ) -> None:
        ws = wb.active
        ws.title = "Overview"

        header = ["Project"] + [format_month_header(y, m) for y, m in periods]
        ws.append(header)
        apply_header_style(ws, 1)

        for item in project_data:
            project = item["project"]
            scores = item["scores"]
            row = [project.name]
            for period in periods:
                data = scores.get(period)
                score = data["scores"].score if data else None
                row.append(score)
            ws.append(row)

            # Traffic light
            current_row = ws.max_row
            for col_idx in range(2, 2 + len(periods)):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                apply_traffic_light(cell, cell.value, 80)

        widths = {"A": 30}
        for i in range(len(periods)):
            widths[get_column_letter(2 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 2, 2)

    def _build_dimensions_sheet(
        self,
        wb: Workbook,
        project_data: list[dict],
        periods: list[tuple[int, int]],
    ) -> None:
        ws = wb.create_sheet("Dimensions")

        dim_keys = [
            ("p_time", "P_time — Schedule"),
            ("p_cost", "P_cost — Budget"),
            ("p_quality", "P_quality — Quality"),
            ("p_value", "P_value — Strategic Value"),
            ("p_satisfaction", "P_satisfaction — Satisfaction"),
            ("p_flow", "P_flow — Flow"),
            ("p_engineering", "P_engineering — Engineering"),
            ("p_risk", "P_risk — Risk"),
        ]

        for dim_key, dim_name in dim_keys:
            # Dimension header
            ws.append([dim_name])
            ws.cell(row=ws.max_row, column=1).font = apply_row_style.__defaults__ and None
            from openpyxl.styles import Font
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

            # Column headers
            header = ["Project"] + [format_month_header(y, m) for y, m in periods]
            ws.append(header)
            apply_header_style(ws, ws.max_row)

            # Project rows
            target = self._get_dimension_target(dim_key)
            for item in project_data:
                project = item["project"]
                scores = item["scores"]
                row = [project.name]
                for period in periods:
                    data = scores.get(period)
                    value = None
                    if data:
                        value = getattr(data["scores"].dimensions, dim_key, None)
                    row.append(value)
                ws.append(row)

                current_row = ws.max_row
                for col_idx in range(2, 2 + len(periods)):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.border = THIN_BORDER
                    if target:
                        apply_traffic_light(cell, cell.value, target)

            ws.append([])  # Spacer row

        widths = {"A": 30}
        for i in range(len(periods)):
            widths[get_column_letter(2 + i)] = 12
        set_column_widths(ws, widths)

    # --- Helpers ---

    @staticmethod
    def _generate_periods(
        start_year: int, start_month: int, end_year: int, end_month: int
    ) -> list[tuple[int, int]]:
        """Generate list of (year, month) tuples for the range."""
        periods = []
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            periods.append((year, month))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return periods

    def _get_target_for_metric(self, key: str, level: int) -> str | None:
        """Get display target for a metric key."""
        if level == 0:
            return None
        if level == 1:
            return str(self._get_dimension_target(key) or "-")
        try:
            return str(self.config.get_target(key))
        except (KeyError, ValueError):
            return None

    def _get_dimension_target(self, dim_key: str) -> float | None:
        """Get target for a dimension (default 80)."""
        return 80

    @staticmethod
    def _extract_value(key: str, level: int, score_data: dict | None) -> int | float | None:
        """Extract the right value for a metric row from computed score data."""
        if score_data is None:
            return None
        if level == 0:
            return score_data["scores"].score
        if level == 1:
            return getattr(score_data["scores"].dimensions, key, None)
        # Level 2: indicator value
        return getattr(score_data["indicators"], key, None)

    @staticmethod
    def _parse_target(target: str | None) -> float | None:
        """Parse target string to float, returns None if not numeric."""
        if not target or target == "-":
            return None
        try:
            return float(target)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _save_to_bytes(wb: Workbook) -> BytesIO:
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/test_export_service.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/app/services/export_service.py backend/tests/test_export_service.py
git commit -m "feat: add ExportService for project detail and global XLSX"
```

---

### Task 5: Create export API endpoints

**Files:**
- Create: `backend/app/api/exports.py`
- Modify: `backend/app/main.py` (add router)
- Test: `backend/tests/test_export_api.py`

**Step 1: Write the test**

```python
"""Tests for export API endpoints."""

import pytest
import pytest_asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB
from app.models.project import ProjectDB


@pytest_asyncio.fixture
async def export_project(db_session: AsyncSession) -> ProjectDB:
    """Create a project with metrics for export tests."""
    project = ProjectDB(
        id=str(uuid4()),
        name="API Export Test",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="in_progress",
    )
    db_session.add(project)

    metrics = MetricsDB(
        project_id=str(project.id),
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        period_year=2025,
        period_month=1,
        snapshot_type="cumulative",
        budget_total=Decimal("100000"),
        cost_to_date=Decimal("45000"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        bugs_total=5,
        tasks_completed=100,
        governance_exceptions=0,
        sev1_incident=False,
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(project)
    return project


class TestProjectExportEndpoint:
    @pytest.mark.asyncio
    async def test_returns_xlsx(self, client: AsyncClient, export_project: ProjectDB):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-01"},
        )
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_includes_filename(self, client: AsyncClient, export_project: ProjectDB):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 200
        disposition = response.headers.get("content-disposition", "")
        assert "API_Export_Test" in disposition or "api_export_test" in disposition.lower()

    @pytest.mark.asyncio
    async def test_invalid_project_returns_404(self, client: AsyncClient):
        fake_id = str(uuid4())
        response = await client.get(
            f"/api/exports/project/{fake_id}",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_snapshot_type_parameter(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-01", "snapshot_type": "punctual"},
        )
        assert response.status_code == 200


class TestGlobalExportEndpoint:
    @pytest.mark.asyncio
    async def test_returns_xlsx(self, client: AsyncClient, export_project: ProjectDB):
        response = await client.get(
            "/api/exports/global",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @pytest.mark.asyncio
    async def test_returns_xlsx_even_with_no_projects(self, client: AsyncClient):
        response = await client.get(
            "/api/exports/global",
            params={"start": "2025-01", "end": "2025-01"},
        )
        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_export_api.py -v`
Expected: FAIL — import error or 404.

**Step 3: Write endpoint implementation**

Create `backend/app/api/exports.py`:

```python
"""XLSX export endpoints."""

import re
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.services.export_service import ExportService

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _parse_month_param(value: str) -> tuple[int, int]:
    """Parse 'YYYY-MM' string to (year, month) tuple."""
    match = re.match(r"^(\d{4})-(\d{2})$", value)
    if not match:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}. Use YYYY-MM.")
    return int(match.group(1)), int(match.group(2))


def _sanitize_filename(name: str) -> str:
    """Sanitize project name for use in filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


@router.get("/exports/project/{project_id}")
@limiter.limit("10/minute")
async def export_project_detail(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    start: str = Query(..., description="Start period (YYYY-MM)"),
    end: str = Query(..., description="End period (YYYY-MM)"),
    snapshot_type: str = Query("cumulative", description="cumulative or punctual"),
) -> StreamingResponse:
    """Export project scorecard data to XLSX."""
    project = await get_project_or_404(db, project_id)
    start_year, start_month = _parse_month_param(start)
    end_year, end_month = _parse_month_param(end)

    service = ExportService(config)
    output = await service.export_project_detail(
        db=db,
        project_id=str(project_id),
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        snapshot_type=snapshot_type,
    )

    filename = f"{_sanitize_filename(project.name)}_scorecard_{start}_{end}.xlsx"
    return StreamingResponse(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/exports/global")
@limiter.limit("10/minute")
async def export_global_dashboard(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    start: str = Query(..., description="Start period (YYYY-MM)"),
    end: str = Query(..., description="End period (YYYY-MM)"),
    snapshot_type: str = Query("cumulative", description="cumulative or punctual"),
) -> StreamingResponse:
    """Export global dashboard data to XLSX."""
    start_year, start_month = _parse_month_param(start)
    end_year, end_month = _parse_month_param(end)

    service = ExportService(config)
    output = await service.export_global_dashboard(
        db=db,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        snapshot_type=snapshot_type,
    )

    filename = f"global_scorecard_{start}_{end}.xlsx"
    return StreamingResponse(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

**Step 4: Register router in main.py**

Add to `backend/app/main.py` imports (near other router imports):

```python
from app.api import exports as exports_router
```

Add after the last `app.include_router` line:

```python
app.include_router(exports_router.router, prefix="/api", tags=["exports"])
```

**Step 5: Run tests**

Run: `cd backend && pytest tests/test_export_api.py -v`
Expected: All PASS.

**Step 6: Run full backend test suite**

Run: `cd backend && pytest --tb=short -q`
Expected: All existing tests still pass.

**Step 7: Commit**

```bash
git add backend/app/api/exports.py backend/app/main.py backend/tests/test_export_api.py
git commit -m "feat: add XLSX export API endpoints (project detail + global)"
```

---

### Task 6: Create frontend export API service and hook

**Files:**
- Create: `frontend/src/services/api/exports.ts`
- Modify: `frontend/src/services/api/index.ts` (add re-export)
- Create: `frontend/src/hooks/useExport.ts`

**Step 1: Create API service**

Create `frontend/src/services/api/exports.ts`:

```typescript
import api from './client';

export interface ExportParams {
  start: string;
  end: string;
  snapshotType?: string;
}

export const exportsApi = {
  exportProjectDetail: async (
    projectId: string,
    params: ExportParams,
  ): Promise<Blob> => {
    const response = await api.get(
      `/exports/project/${projectId}`,
      {
        params: {
          start: params.start,
          end: params.end,
          snapshot_type: params.snapshotType ?? 'cumulative',
        },
        responseType: 'blob',
      },
    );
    return response.data;
  },

  exportGlobalDashboard: async (params: ExportParams): Promise<Blob> => {
    const response = await api.get(
      '/exports/global',
      {
        params: {
          start: params.start,
          end: params.end,
          snapshot_type: params.snapshotType ?? 'cumulative',
        },
        responseType: 'blob',
      },
    );
    return response.data;
  },
};
```

**Step 2: Add re-export to index**

Add to `frontend/src/services/api/index.ts`:

```typescript
// Exports API
export { exportsApi } from './exports';
```

**Step 3: Create export hook**

Create `frontend/src/hooks/useExport.ts`:

```typescript
import { useState } from 'react';
import { exportsApi } from '../services/api/exports';
import type { ExportParams } from '../services/api/exports';

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function formatPeriod(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

interface UseExportReturn {
  exportProject: (
    projectId: string,
    projectName: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ) => Promise<void>;
  exportGlobal: (
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ) => Promise<void>;
  isExporting: boolean;
  error: string | null;
}

export function useExport(): UseExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportProject = async (
    projectId: string,
    projectName: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const start = formatPeriod(fromYear, fromMonth);
      const end = formatPeriod(toYear, toMonth);
      const params: ExportParams = { start, end, snapshotType };
      const blob = await exportsApi.exportProjectDetail(projectId, params);
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      downloadBlob(blob, `${safeName}_scorecard_${start}_${end}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportGlobal = async (
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const start = formatPeriod(fromYear, fromMonth);
      const end = formatPeriod(toYear, toMonth);
      const params: ExportParams = { start, end, snapshotType };
      const blob = await exportsApi.exportGlobalDashboard(params);
      downloadBlob(blob, `global_scorecard_${start}_${end}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return { exportProject, exportGlobal, isExporting, error };
}
```

**Step 4: Verify frontend compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/services/api/exports.ts frontend/src/services/api/index.ts frontend/src/hooks/useExport.ts
git commit -m "feat: add frontend export API service and useExport hook"
```

---

### Task 7: Update SnapshotManager with export UI

Replace the disabled CSV stub with functional date range pickers, snapshot type selector, and XLSX export button.

**Files:**
- Modify: `frontend/src/components/ProjectDetail/SnapshotManager.tsx`

**Step 1: Update SnapshotManager**

Replace the full content of `SnapshotManager.tsx` with:

```typescript
import { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MonthYearPicker } from '@/components/ui/month-year-picker';
import { NativeSelect } from '@/components/ui/native-select';
import { FileDown, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import HistoricalCaptureSection from './HistoricalCaptureSection';
import { useExport } from '../../hooks/useExport';

interface SnapshotManagerProps {
  readonly projectId: string;
  readonly projectName: string;
}

export default function SnapshotManager({
  projectId,
  projectName,
}: SnapshotManagerProps): JSX.Element {
  const currentDate = new Date();
  const [isExportExpanded, setIsExportExpanded] = useState(false);

  const [fromYear, setFromYear] = useState(currentDate.getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(currentDate.getFullYear());
  const [toMonth, setToMonth] = useState(currentDate.getMonth() + 1);
  const [snapshotType, setSnapshotType] = useState('cumulative');

  const { exportProject, isExporting, error } = useExport();

  const handleExport = async (): Promise<void> => {
    await exportProject(
      projectId,
      projectName,
      fromYear,
      fromMonth,
      toYear,
      toMonth,
      snapshotType,
    );
  };

  const monthCount = (toYear - fromYear) * 12 + (toMonth - fromMonth) + 1;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <HistoricalCaptureSection projectId={projectId} />

      <Card>
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setIsExportExpanded(!isExportExpanded)}
        >
          <CardTitle className="flex items-center gap-2">
            {isExportExpanded ? (
              <ChevronDown className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
            <FileDown className="h-5 w-5" />
            Export
          </CardTitle>
          {isExportExpanded && (
            <CardDescription>
              Export project scorecard to XLSX
            </CardDescription>
          )}
        </CardHeader>
        {isExportExpanded && (
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-muted-foreground">From</span>
              <MonthYearPicker
                month={fromMonth}
                year={fromYear}
                onMonthChange={setFromMonth}
                onYearChange={setFromYear}
                disabled={isExporting}
              />
              <span className="text-sm text-muted-foreground">to</span>
              <MonthYearPicker
                month={toMonth}
                year={toYear}
                onMonthChange={setToMonth}
                onYearChange={setToYear}
                disabled={isExporting}
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Snapshot</span>
              <NativeSelect
                value={snapshotType}
                onChange={(e) => setSnapshotType(e.target.value)}
                disabled={isExporting}
              >
                <option value="cumulative">Cumulative</option>
                <option value="punctual">Punctual</option>
              </NativeSelect>
            </div>

            {monthCount > 0 && (
              <p className="text-sm text-muted-foreground">
                Will export {monthCount} month{monthCount > 1 ? 's' : ''} of data.
              </p>
            )}

            <Button
              onClick={handleExport}
              disabled={isExporting || monthCount <= 0}
            >
              {isExporting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <FileDown className="mr-2 h-4 w-4" />
                  Export XLSX
                </>
              )}
            </Button>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                {error}
              </div>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
}
```

**Step 2: Update SnapshotManager props in parent**

Check where `SnapshotManager` is used and add the `projectName` prop. It's used in `ProjectDetail.tsx`. Find the usage and add `projectName={project.name}`.

Look for: `<SnapshotManager projectId=` in `frontend/src/pages/ProjectDetail.tsx` and add the `projectName` prop.

**Step 3: Check if NativeSelect exists**

Verify `frontend/src/components/ui/native-select.tsx` exists. If not, use a plain `<select>` element with Tailwind classes instead.

**Step 4: Verify frontend compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/components/ProjectDetail/SnapshotManager.tsx frontend/src/pages/ProjectDetail.tsx
git commit -m "feat: add XLSX export UI to project detail SnapshotManager"
```

---

### Task 8: Add export to Global Dashboard

**Files:**
- Modify: `frontend/src/pages/GlobalDashboard/index.tsx`

**Step 1: Add export section to GlobalDashboard**

Add the export UI to the Global Dashboard page. Import the needed components and add a collapsible export card similar to the one in SnapshotManager. Place it at the top of the page content.

Use the same pattern: MonthYearPicker for from/to, NativeSelect for snapshot type, Button with loading state. Use `useExport().exportGlobal` for the handler.

**Step 2: Verify frontend compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/pages/GlobalDashboard/index.tsx
git commit -m "feat: add XLSX export to Global Dashboard"
```

---

### Task 9: Run full test suite and verify

**Step 1: Run backend tests**

Run: `cd backend && pytest --tb=short -q`
Expected: All tests pass (existing + new export tests).

**Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All tests pass.

**Step 4: Manual smoke test**

Start backend and frontend:
```bash
cd backend && python run_server.py &
cd frontend && npm run dev &
```

1. Open a project detail page → expand Export section → select date range → click Export XLSX → verify file downloads and opens in Excel/LibreOffice
2. Open Global Dashboard → expand Export → select date range → click Export XLSX → verify file downloads
3. Verify both files have 3 sheets each with proper formatting

**Step 5: Commit**

If any fixes were needed, commit them:
```bash
git add -A
git commit -m "fix: export adjustments from smoke testing"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add openpyxl dependency | `requirements.txt` |
| 2 | Export metric definitions | `export_definitions.py` + test |
| 3 | Export helpers (styling, methodology) | `export_helpers.py` + test |
| 4 | ExportService (core logic) | `export_service.py` + test |
| 5 | API endpoints | `exports.py` + `main.py` + test |
| 6 | Frontend API service + hook | `exports.ts` + `useExport.ts` |
| 7 | SnapshotManager UI | `SnapshotManager.tsx` |
| 8 | GlobalDashboard export UI | `GlobalDashboard/index.tsx` |
| 9 | Full test suite + smoke test | All |
