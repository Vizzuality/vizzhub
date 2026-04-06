"""Registry service — validation and helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


_TYPE_VALIDATORS: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "user": str,
    "number": (int, float),
    "boolean": bool,
}


def _validate_field_type(value: object, col: dict) -> str | None:
    """Validate a single field value against its column definition."""
    label = col["label"]
    col_type = col["type"]

    expected = _TYPE_VALIDATORS.get(col_type)
    if expected and not isinstance(value, expected):
        type_name = expected.__name__ if isinstance(expected, type) else col_type
        return f"Field '{label}' must be a {type_name}"

    if col_type == "date" and isinstance(value, str):
        try:
            date.fromisoformat(value)
        except ValueError:
            return f"Field '{label}' must be a valid date (YYYY-MM-DD)"

    if col_type == "select":
        options = col.get("options", [])
        if value not in options:
            return f"Field '{label}' must be one of: {', '.join(options)}"

    return None


def _validate_column(
    col: dict, value: object, partial: bool,
) -> str | None:
    """Validate a single column value. Returns error message or None."""
    if col["type"] in ("computed", "attachment"):
        return None

    is_missing = value is None or (isinstance(value, str) and value.strip() == "")

    if col.get("required") and is_missing and not partial:
        return f"Field '{col['label']}' is required"

    if is_missing:
        return None

    return _validate_field_type(value, col)


def validate_row_data(
    schema: list[dict], data: dict, *, partial: bool = False
) -> list[str]:
    """Validate row data against registry type schema. Returns error list."""
    columns_by_key = {col["key"]: col for col in schema}

    errors = [
        err
        for key, col in columns_by_key.items()
        if (err := _validate_column(col, data.get(key), partial))
    ]

    unknown_keys = set(data.keys()) - set(columns_by_key.keys())
    if unknown_keys:
        errors.append(f"Unknown fields: {', '.join(sorted(unknown_keys))}")

    return errors


def strip_computed_keys(schema: list[dict], data: dict) -> dict:
    """Remove computed and attachment field keys from row data before storage."""
    computed_keys = {col["key"] for col in schema if col["type"] in ("computed", "attachment")}
    if not computed_keys:
        return data
    return {k: v for k, v in data.items() if k not in computed_keys}


def _gather_numeric_values(data: dict, fields: list[str]) -> list[float] | None:
    """Extract numeric values for formula fields. Returns None if any are missing."""
    values = []
    for f in fields:
        v = data.get(f)
        if v is None or not isinstance(v, (int, float)):
            return None
        values.append(v)
    return values


def _apply_formula(operation: str, values: list[float]) -> float | None:
    if operation == "multiply":
        result = 1.0
        for v in values:
            result *= v
        return result
    if operation == "sum":
        return sum(values)
    return None


def compute_row_fields(schema: list[dict], data: dict) -> dict:
    """Add computed field values to row data for serialization."""
    result = dict(data)
    for col in schema:
        if col["type"] != "computed":
            continue
        formula = col.get("formula")
        if not formula:
            continue
        values = _gather_numeric_values(data, formula["fields"])
        result[col["key"]] = _apply_formula(formula["operation"], values) if values else None
    return result


async def get_next_row_index(
    db: AsyncSession, node_id, year: int | None = None
) -> int:
    """Get the next row_index for a registry node (optionally within a year)."""
    from app.modules.iso_docs.models.registry_row import RegistryRowDB

    query = select(func.coalesce(func.max(RegistryRowDB.row_index), -1) + 1).where(
        RegistryRowDB.node_id == node_id
    )
    if year is not None:
        query = query.where(RegistryRowDB.year == year)
    result = await db.execute(query)
    return result.scalar_one()
