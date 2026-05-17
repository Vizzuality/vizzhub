"""Integration test: full playbook workflow."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Create the dev user so FK constraints on created_by_id pass."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == DEBUG_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEBUG_USER_ID, email="dev@test.com"))
        await db_session.flush()


@pytest.mark.asyncio
async def test_full_playbook_workflow(client: AsyncClient):
    """Create tree, add content, edit, check versions."""
    # 1. Create a group
    group = await client.post(
        "/api/playbook/nodes",
        json={"title": "Engineering", "type": "group"},
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    # 2. Create a page under the group
    page = await client.post(
        "/api/playbook/nodes",
        json={"title": "Setup Guide", "type": "page", "parent_id": group_id},
    )
    assert page.status_code == 201
    page_id = page.json()["id"]

    # 3. Save content
    save1 = await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "# Setup\n\nInstall dependencies.", "expected_version": 0},
    )
    assert save1.json()["version"] == 1

    # 4. Edit content
    save2 = await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "# Setup\n\nRun `npm install`.", "expected_version": 1},
    )
    assert save2.json()["version"] == 2

    # 5. Verify latest content
    content = await client.get(f"/api/playbook/pages/{page_id}")
    assert content.json()["content"] == "# Setup\n\nRun `npm install`."
    assert content.json()["version"] == 2

    # 6. Check version history
    versions = await client.get(f"/api/playbook/pages/{page_id}/versions")
    assert len(versions.json()) == 2

    # 7. Retrieve old version
    v1 = await client.get(f"/api/playbook/pages/{page_id}/versions/1")
    assert v1.json()["content"] == "# Setup\n\nInstall dependencies."

    # 8. Tree shows correct structure
    tree = await client.get("/api/playbook/tree")
    assert len(tree.json()) == 1
    assert tree.json()[0]["title"] == "Engineering"
    assert len(tree.json()[0]["children"]) == 1

    # 9. Toggle public
    await client.patch(
        f"/api/playbook/nodes/{page_id}",
        json={"is_public": True},
    )
    content2 = await client.get(f"/api/playbook/pages/{page_id}")
    assert content2.json()["is_public"] is True

    # 10. Delete group cascades
    delete = await client.delete(f"/api/playbook/nodes/{group_id}")
    assert delete.json()["deleted_count"] == 2

    tree2 = await client.get("/api/playbook/tree")
    assert tree2.json() == []
