"""Tests for registry_service — validation, computed fields, stripping."""

import pytest

from app.modules.iso_docs.services.registry_service import (
    compute_row_fields,
    strip_computed_keys,
    validate_row_data,
)

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
    assert any("bool" in e for e in errors)


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


# --- Computed field tests ---

SCHEMA_WITH_COMPUTED = [
    {"key": "probability", "label": "Probability", "type": "number", "required": True},
    {"key": "impact", "label": "Impact", "type": "number", "required": True},
    {
        "key": "evaluation",
        "label": "Evaluation",
        "type": "computed",
        "formula": {"operation": "multiply", "fields": ["probability", "impact"]},
        "conditional_format": [
            {"min": 1, "max": 2, "color": "#22c55e", "label": "Low"},
            {"min": 3, "max": 4, "color": "#eab308", "label": "Moderate"},
            {"min": 6, "max": 9, "color": "#ef4444", "label": "High"},
        ],
    },
    {"key": "notes", "label": "Notes", "type": "string", "required": False},
]


def test_computed_field_skipped_in_validation():
    errors = validate_row_data(
        SCHEMA_WITH_COMPUTED, {"probability": 2, "impact": 3}
    )
    assert errors == []


def test_computed_field_not_required():
    errors = validate_row_data(
        SCHEMA_WITH_COMPUTED, {"probability": 2, "impact": 3}
    )
    assert not any("Evaluation" in e for e in errors)


def test_compute_row_fields_multiply():
    data = {"probability": 2, "impact": 3, "notes": "test"}
    result = compute_row_fields(SCHEMA_WITH_COMPUTED, data)
    assert result["evaluation"] == 6
    assert result["probability"] == 2
    assert result["notes"] == "test"


def test_compute_row_fields_null_source():
    data = {"probability": 2, "impact": None}
    result = compute_row_fields(SCHEMA_WITH_COMPUTED, data)
    assert result["evaluation"] is None


def test_compute_row_fields_missing_source():
    data = {"probability": 2}
    result = compute_row_fields(SCHEMA_WITH_COMPUTED, data)
    assert result["evaluation"] is None


def test_compute_row_fields_sum():
    schema = [
        {"key": "a", "label": "A", "type": "number", "required": False},
        {"key": "b", "label": "B", "type": "number", "required": False},
        {
            "key": "total",
            "label": "Total",
            "type": "computed",
            "formula": {"operation": "sum", "fields": ["a", "b"]},
        },
    ]
    result = compute_row_fields(schema, {"a": 10, "b": 20})
    assert result["total"] == 30


def test_strip_computed_keys():
    data = {"probability": 2, "impact": 3, "evaluation": 6, "notes": "x"}
    result = strip_computed_keys(SCHEMA_WITH_COMPUTED, data)
    assert "evaluation" not in result
    assert result == {"probability": 2, "impact": 3, "notes": "x"}


def test_strip_computed_keys_no_computed():
    data = {"name": "X", "category": "A"}
    result = strip_computed_keys(SCHEMA, data)
    assert result == data


# --- Attachment field type tests ---

SCHEMA_WITH_ATTACHMENT = [
    {"key": "name", "label": "Name", "type": "string", "required": True},
    {"key": "certificate", "label": "Certificate", "type": "attachment"},
]


def test_attachment_field_skipped_in_validation():
    errors = validate_row_data(SCHEMA_WITH_ATTACHMENT, {"name": "X"})
    assert errors == []


def test_attachment_field_stripped_from_data():
    data = {"name": "X", "certificate": "should-be-stripped"}
    result = strip_computed_keys(SCHEMA_WITH_ATTACHMENT, data)
    assert "certificate" not in result
    assert result == {"name": "X"}
