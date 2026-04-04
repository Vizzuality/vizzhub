"""Registry service — validation and helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _validate_field_type(value: object, col: dict) -> str | None:
    """Validate a single field value against its column definition."""
    label = col["label"]
    col_type = col["type"]

    if col_type in ("string", "user") and not isinstance(value, str):
        return f"Field '{label}' must be a string"
    if col_type == "number" and not isinstance(value, (int, float)):
        return f"Field '{label}' must be a number"
    if col_type == "boolean" and not isinstance(value, bool):
        return f"Field '{label}' must be a boolean"
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


def validate_row_data(
    schema: list[dict], data: dict, *, partial: bool = False
) -> list[str]:
    """Validate row data against registry type schema. Returns error list."""
    errors: list[str] = []
    columns_by_key = {col["key"]: col for col in schema}

    for key, col in columns_by_key.items():
        if col["type"] in ("computed", "attachment"):
            continue

        value = data.get(key)
        is_missing = value is None or (isinstance(value, str) and value.strip() == "")

        if col.get("required") and is_missing and not partial:
            errors.append(f"Field '{col['label']}' is required")
            continue

        if is_missing:
            continue

        error = _validate_field_type(value, col)
        if error:
            errors.append(error)

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


def compute_row_fields(schema: list[dict], data: dict) -> dict:
    """Add computed field values to row data for serialization."""
    result = dict(data)
    for col in schema:
        if col["type"] != "computed":
            continue
        formula = col.get("formula")
        if not formula:
            continue
        fields = formula["fields"]
        values = []
        for f in fields:
            v = data.get(f)
            if v is None or not isinstance(v, (int, float)):
                values = None
                break
            values.append(v)
        if values is None:
            result[col["key"]] = None
            continue
        operation = formula["operation"]
        if operation == "multiply":
            computed = 1
            for v in values:
                computed *= v
            result[col["key"]] = computed
        elif operation == "sum":
            result[col["key"]] = sum(values)
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
