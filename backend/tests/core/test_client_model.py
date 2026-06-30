import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB


@pytest.mark.asyncio
async def test_project_links_to_client(db_session):
    client = ClientDB(name="Acme Foundation", slug="acme-foundation")
    db_session.add(client)
    await db_session.flush()
    project = ProjectDB(name="A Project", client_id=client.id)
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    assert project.client_id == client.id
    assert client.is_active is True
