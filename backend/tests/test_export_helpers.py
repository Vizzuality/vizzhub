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
        assert cell.fill.start_color.rgb == "004CAF50"

    def test_yellow_when_near_target(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=70)
        apply_traffic_light(cell, 70, 80)
        assert cell.fill.start_color.rgb == "00FFC107"

    def test_red_when_below_threshold(self):
        wb = Workbook()
        ws = wb.active
        cell = ws.cell(row=1, column=1, value=50)
        apply_traffic_light(cell, 50, 80)
        assert cell.fill.start_color.rgb == "00F44336"

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
