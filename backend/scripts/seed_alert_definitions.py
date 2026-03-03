"""Seed alert_definitions and message_templates tables from CSV."""

import csv
import json
import asyncio
import sys
import argparse
from pathlib import Path
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.modules.scorecard.models.slack import AlertDefinitionDB, MessageTemplateDB


def _read_csv(filename: str) -> list[dict]:
    """Read data from CSV file (sync operation)."""
    csv_path = Path(__file__).parent.parent / "seeds" / filename
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def seed_alert_definitions(db: AsyncSession | None = None, force: bool = False) -> None:
    """Seed alert definitions and message templates from CSV if tables are empty.

    Args:
        db: Optional database session. If not provided, creates its own session.
        force: If True, truncate tables before seeding.
    """
    should_close = db is None
    if db is None:
        db = async_session_maker()
        await db.__aenter__()

    try:
        if force:
            await db.execute(text("TRUNCATE TABLE message_templates RESTART IDENTITY CASCADE"))
            await db.execute(text("TRUNCATE TABLE alert_definitions RESTART IDENTITY CASCADE"))
            await db.commit()
            print("✓ Tables truncated")

        result = await db.execute(select(func.count()).select_from(AlertDefinitionDB))
        count = result.scalar()

        if count > 0 and not force:
            print(f"✓ Alert definitions already seeded ({count} rows)")
            return

        alert_rows = await asyncio.to_thread(_read_csv, "alert_definitions.csv")
        alert_name_to_id = {}

        for row in alert_rows:
            config_str = row["config_json"].strip() if row["config_json"] else "{}"
            try:
                config_json = json.loads(config_str)
            except json.JSONDecodeError:
                config_json = {}
            alert = AlertDefinitionDB(
                name=row["name"],
                description=row["description"] if row["description"] else None,
                category=row["category"],
                channel_type=row["channel_type"],
                schedule=row["schedule"],
                is_enabled=row["is_enabled"].lower() == "true",
                config_json=config_json,
            )
            db.add(alert)
            await db.flush()
            alert_name_to_id[alert.name] = alert.id

        print(f"✓ Seeded {len(alert_rows)} alert definitions")

        template_rows = await asyncio.to_thread(_read_csv, "message_templates.csv")

        for row in template_rows:
            alert_name = row["alert_name"]
            if alert_name not in alert_name_to_id:
                print(f"⚠ Skipping template for unknown alert: {alert_name}")
                continue

            template = MessageTemplateDB(
                alert_definition_id=alert_name_to_id[alert_name],
                template_type=row["template_type"],
                message_template=row["message_template"],
                is_active=row["is_active"].lower() == "true",
            )
            db.add(template)

        await db.commit()
        print(f"✓ Seeded {len(template_rows)} message templates")

    finally:
        if should_close:
            await db.__aexit__(None, None, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed alert definitions from CSV")
    parser.add_argument("--force", action="store_true", help="Truncate tables before seeding")
    args = parser.parse_args()

    asyncio.run(seed_alert_definitions(force=args.force))
