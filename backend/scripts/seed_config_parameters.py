"""Seed config_parameters table from CSV."""

import csv
import asyncio
import sys
import argparse
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.models.config import ConfigParameter


def _read_csv_parameters() -> list[dict]:
    """Read config parameters from CSV file (sync operation)."""
    csv_path = Path(__file__).parent.parent / "seeds" / "config_parameters.csv"
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def seed_config_parameters(db: AsyncSession | None = None, force: bool = False) -> None:
    """Seed config parameters from CSV if table is empty.

    Args:
        db: Optional database session. If not provided, creates its own session.
        force: If True, truncate table before seeding.
    """
    should_close = db is None
    if db is None:
        db = async_session_maker()
        await db.__aenter__()

    try:
        # Truncate if force flag is set
        if force:
            await db.execute(text("TRUNCATE TABLE config_parameters RESTART IDENTITY CASCADE"))
            await db.commit()
            print("✓ Table truncated")

        # Check if already seeded
        result = await db.execute(
            select(func.count()).select_from(ConfigParameter)
        )
        count = result.scalar()

        if count > 0 and not force:
            print(f"✓ Config parameters already seeded ({count} rows)")
            return

        # Read CSV (sync operation extracted to avoid async file I/O issue)
        rows = await asyncio.to_thread(_read_csv_parameters)
        parameters = [
            ConfigParameter(
                category=row["category"],
                name=row["name"],
                value=Decimal(row["value"]),
                unit=row["unit"] if row["unit"] else None,
                notes=row["notes"] if row["notes"] else None
            )
            for row in rows
        ]

        db.add_all(parameters)
        await db.commit()
        print(f"✓ Seeded {len(parameters)} config parameters")
    finally:
        if should_close:
            await db.__aexit__(None, None, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed config parameters from CSV")
    parser.add_argument("--force", action="store_true", help="Truncate table before seeding")
    args = parser.parse_args()

    asyncio.run(seed_config_parameters(force=args.force))
