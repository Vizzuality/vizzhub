"""Seed capacity_plans table from capacity_seed.json.

Run against any environment:
    python scripts/seed_capacity_planner.py [path/to/capacity_seed.json]

Defaults to capacity_seed.json in current directory.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings  # noqa: F401 — initialises config before DB import
from app.database import AsyncSessionLocal
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.capacity.models.capacity_plan import CapacityPlanDB


async def main(json_path: str) -> None:
    with open(json_path) as f:
        records = json.load(f)

    print(f"Loaded {len(records)} records from {json_path}")

    async with AsyncSessionLocal() as db:
        # Build lookup maps
        projects_result = await db.execute(select(ProjectDB.id, ProjectDB.name))
        project_map = {row.name: row.id for row in projects_result.all()}

        users_result = await db.execute(select(UserDB.id, UserDB.email))
        email_map = {row.email: row.id for row in users_result.all()}

        # Get a default user for created_by/updated_by (first user in DB)
        first_user_result = await db.execute(select(UserDB.id).limit(1))
        seed_user_id = first_user_result.scalar_one_or_none()
        if not seed_user_id:
            print("ERROR: No users found in database")
            return

        skipped_projects: set[str] = set()
        skipped_emails: set[str] = set()
        values = []

        for rec in records:
            project_id = project_map.get(rec["project_name"])
            user_id = email_map.get(rec["user_email"])

            if not project_id:
                skipped_projects.add(rec["project_name"])
                continue
            if not user_id:
                skipped_emails.add(rec["user_email"])
                continue

            values.append({
                "project_id": project_id,
                "user_id": user_id,
                "week_start": rec["week_start"],
                "percentage": rec["percentage"],
                "created_by": seed_user_id,
                "updated_by": seed_user_id,
            })

        if values:
            # Batch insert with ON CONFLICT DO NOTHING
            BATCH_SIZE = 500
            inserted = 0
            for i in range(0, len(values), BATCH_SIZE):
                batch = values[i : i + BATCH_SIZE]
                stmt = pg_insert(CapacityPlanDB).values(batch)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_capacity_plan_cell")
                result = await db.execute(stmt)
                inserted += result.rowcount
            await db.commit()
            print(f"Inserted {inserted} records (skipped {len(values) - inserted} duplicates)")
        else:
            print("No valid records to insert")

        if skipped_projects:
            print(f"Skipped projects (not in DB): {sorted(skipped_projects)}")
        if skipped_emails:
            print(f"Skipped emails (not in DB): {sorted(skipped_emails)}")


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "capacity_seed.json"
    asyncio.run(main(json_path))
