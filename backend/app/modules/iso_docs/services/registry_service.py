"""Registry service — validation and helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def validate_row_data(
    schema: list[dict], data: dict, *, partial: bool = False
) -> list[str]:
    """Validate row data against registry type schema. Returns error list."""
    errors: list[str] = []
    columns_by_key = {col["key"]: col for col in schema}

    for key, col in columns_by_key.items():
        value = data.get(key)
        is_missing = value is None or (isinstance(value, str) and value.strip() == "")

        if col.get("required") and is_missing and not partial:
            errors.append(f"Field '{col['label']}' is required")
            continue

        if is_missing:
            continue

        col_type = col["type"]
        if col_type in ("string", "user") and not isinstance(value, str):
            errors.append(f"Field '{col['label']}' must be a string")
        elif col_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{col['label']}' must be a number")
        elif col_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{col['label']}' must be a boolean")
        elif col_type == "date" and isinstance(value, str):
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"Field '{col['label']}' must be a valid date (YYYY-MM-DD)")
        elif col_type == "select":
            options = col.get("options", [])
            if value not in options:
                errors.append(
                    f"Field '{col['label']}' must be one of: {', '.join(options)}"
                )

    unknown_keys = set(data.keys()) - set(columns_by_key.keys())
    if unknown_keys:
        errors.append(f"Unknown fields: {', '.join(sorted(unknown_keys))}")

    return errors


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
