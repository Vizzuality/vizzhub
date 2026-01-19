"""Seed config_parameters table from CSV."""

import csv
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.models.config import ConfigParameter


async def seed_config_parameters(db: AsyncSession | None = None) -> None:
    """Seed config parameters from CSV if table is empty.

    Args:
        db: Optional database session. If not provided, creates its own session.
    """
    should_close = db is None
    if db is None:
        db = async_session_maker()
        await db.__aenter__()

    try:
        # Check if already seeded
        result = await db.execute(
            select(func.count()).select_from(ConfigParameter)
        )
        count = result.scalar()

        if count > 0:
            print(f"✓ Config parameters already seeded ({count} rows)")
            return

        # Read CSV
        csv_path = Path(__file__).parent.parent / "seeds" / "config_parameters.csv"
        parameters = []

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parameters.append(ConfigParameter(
                    category=row["category"],
                    name=row["name"],
                    value=Decimal(row["value"]),
                    unit=row["unit"] if row["unit"] else None,
                    notes=row["notes"] if row["notes"] else None
                ))

        db.add_all(parameters)
        await db.commit()
        print(f"✓ Seeded {len(parameters)} config parameters")
    finally:
        if should_close:
            await db.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(seed_config_parameters())
