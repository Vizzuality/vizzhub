"""
Migration script to update config_parameters to use percentage format.

This migration updates target values and units to use consistent percentage format.
Run this script to update existing database records.

Usage:
    python scripts/migrate_percentage_targets.py
    python scripts/migrate_percentage_targets.py --dry-run  # Preview changes
"""

import asyncio
import argparse
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.database import async_session_maker
from app.modules.scorecard.models.config import ConfigParameter


UPDATES = [
    {
        "name": "LT_t",
        "value": Decimal("3"),
        "unit": "days",
        "notes": "Target maximum lead time in business days. Used in P_flow (sub-indicator Lead Time)",
    },
    {
        "name": "DefDensity_t",
        "value": Decimal("3"),
        "unit": "%",
        "notes": "Target max defect density per 100 tasks (3%). Used in P_quality. ≤ target scores 100%.",
    },
    {
        "name": "Escaped_t",
        "value": Decimal("1"),
        "unit": "%",
        "notes": "Target max escaped defects per 100 tasks (1%). Used in P_quality. ≤ target scores 100%.",
    },
    {
        "name": "PR_noReview_t",
        "value": Decimal("2"),
        "unit": "%",
        "notes": "Target max PRs without review (2%). Used in P_risk.",
    },
]


def _detect_changes(param: ConfigParameter, update_data: dict) -> list[str]:
    """Compare current param against update data and return list of change descriptions."""
    changes = []
    if param.value != update_data["value"]:
        changes.append(f"value: {param.value} → {update_data['value']}")
    if param.unit != update_data["unit"]:
        changes.append(f"unit: '{param.unit}' → '{update_data['unit']}'")
    if param.notes != update_data["notes"]:
        changes.append("notes: updated")
    return changes


async def migrate_percentage_targets(dry_run: bool = False) -> None:
    """Update config parameters to use percentage format."""
    async with async_session_maker() as db:
        print("Migrating config parameters to percentage format...")
        print()

        for update_data in UPDATES:
            name = update_data["name"]

            result = await db.execute(
                select(ConfigParameter).where(ConfigParameter.name == name)
            )
            param = result.scalar_one_or_none()

            if param is None:
                print(f"  SKIP: {name} not found in database")
                continue

            changes = _detect_changes(param, update_data)
            if not changes:
                print(f"  OK: {name} - already up to date")
                continue

            print(f"  UPDATE: {name}")
            for change in changes:
                print(f"          {change}")

            if not dry_run:
                await db.execute(
                    update(ConfigParameter)
                    .where(ConfigParameter.name == name)
                    .values(
                        value=update_data["value"],
                        unit=update_data["unit"],
                        notes=update_data["notes"],
                    )
                )

        if not dry_run:
            await db.commit()
            print()
            print("Migration complete.")
        else:
            print()
            print("Dry run complete. No changes made.")
            print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate config parameters to percentage format")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    asyncio.run(migrate_percentage_targets(dry_run=args.dry_run))
