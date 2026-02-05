"""Shared XLSX formatting helpers for export service."""

import calendar

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.config import ScoringConfig
from app.services.export_definitions import DIMENSION_DEFINITIONS, INDICATOR_DEFINITIONS

GREEN_FILL = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFC107", end_color="FFC107", fill_type="solid")
RED_FILL = PatternFill(start_color="F44336", end_color="F44336", fill_type="solid")

HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

DIM_FILL = PatternFill(start_color="E5E7EB", end_color="E5E7EB", fill_type="solid")
DIM_FONT = Font(bold=True, size=11)

SCORE_FONT = Font(bold=True, size=12)
SCORE_FILL = PatternFill(start_color="D1D5DB", end_color="D1D5DB", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)

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
    ws.freeze_panes = f"{get_column_letter(1)}{row + 1}"


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
    ws.freeze_panes = f"{get_column_letter(col)}{row}"


def create_methodology_sheet(wb: Workbook, config: ScoringConfig) -> Worksheet:
    """Create the Methodology sheet with scoring model explanation and current config."""
    ws = wb.create_sheet("Methodology")

    ws.append(["Scoring Methodology"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([])

    ws.append(["Scoring Model"])
    ws.cell(row=3, column=1).font = Font(bold=True, size=12)
    ws.append(["Raw Metrics", "->", "Normalized Indicators (0-1)", "->", "Weighted Scores (0-100)"])
    ws.append(["Collectors fetch data from Jira and GitHub. Manual inputs supplement automated data."])
    ws.append(["Indicators are normalized to a 0-1 scale. Scores are weighted averages scaled to 0-100."])
    ws.append([])

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

    ws.append(["Snapshot Types"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    ws.append(["Cumulative", "Project-to-date metrics from start_date to period end"])
    ws.append(["Punctual", "Single month metrics for that period only"])
    ws.append([])

    ws.append(["Global Dimension Weights"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
    ws.append(["Dimension", "Weight"])
    dims = ["time", "cost", "quality", "value", "satisfaction", "flow", "engineering", "risk"]
    for dim in dims:
        weight = config.get_weight("global", dim)
        ws.append([f"P_{dim}", f"{weight:.0%}"])
    ws.append([])

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
