"""Tests for registry_service.validate_row_data."""

import pytest

from app.modules.iso_docs.services.registry_service import validate_row_data

SCHEMA = [
    {"key": "name", "label": "Name", "type": "string", "required": True},
    {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["A", "B"]},
    {"key": "count", "label": "Count", "type": "number", "required": False},
    {"key": "active", "label": "Active", "type": "boolean", "required": False},
    {"key": "start_date", "label": "Start Date", "type": "date", "required": False},
]


def test_valid_data():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "count": 5})
    assert errors == []


def test_missing_required():
    errors = validate_row_data(SCHEMA, {"count": 5})
    assert len(errors) == 2
    assert any("Name" in e for e in errors)
    assert any("Category" in e for e in errors)


def test_invalid_select():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "INVALID"})
    assert len(errors) == 1
    assert "one of" in errors[0]


def test_invalid_number():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "count": "not-a-number"})
    assert any("number" in e for e in errors)


def test_invalid_boolean():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "active": "yes"})
    assert any("boolean" in e for e in errors)


def test_invalid_date():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "start_date": "not-a-date"})
    assert any("date" in e for e in errors)


def test_valid_date():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "start_date": "2025-01-15"})
    assert errors == []


def test_unknown_fields():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "unknown": "val"})
    assert any("Unknown" in e for e in errors)


def test_empty_string_counts_as_missing():
    errors = validate_row_data(SCHEMA, {"name": "  ", "category": "A"})
    assert any("Name" in e for e in errors)


def test_optional_fields_can_be_null():
    errors = validate_row_data(SCHEMA, {"name": "X", "category": "A", "count": None})
    assert errors == []
