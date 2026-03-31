"""Set created_by_id and updated_by_id on all ISO docs records for a given user email.

Usage:
    python scripts/update_iso_docs_owner.py <email>
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401


async def update_owner(email: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            print(f"User not found: {email}")
            sys.exit(1)

        print(f"Found user: {user_id}")

        for table in ("iso_doc_nodes", "iso_doc_versions"):
            r = await db.execute(
                text(f"UPDATE {table} SET created_by_id = :uid WHERE created_by_id IS NULL"),
                {"uid": user_id},
            )
            print(f"  {table}: set created_by_id on {r.rowcount} rows")

        r = await db.execute(
            text("UPDATE iso_doc_nodes SET updated_by_id = :uid WHERE updated_by_id IS NULL"),
            {"uid": user_id},
        )
        print(f"  iso_doc_nodes: set updated_by_id on {r.rowcount} rows")

        await db.commit()
        print("Done")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_iso_docs_owner.py <email>")
        sys.exit(1)
    asyncio.run(update_owner(sys.argv[1]))
