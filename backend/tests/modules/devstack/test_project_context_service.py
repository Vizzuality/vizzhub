"""Tests for DevstackProjectContextService."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_service import (
    DevstackProjectContextService,
    DuplicateSlugError,
    SlugImmutableError,
    ProjectAlreadyLinkedError,
)


@pytest_asyncio.fixture
async def sample_project(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(name="Acme Corp")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_create_and_list(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    ctx = await svc.create(
        slug="acme-corp",
        project_id=sample_project.id,
        description="Private notes for Acme",
    )
    assert ctx.slug == "acme-corp"
    assert ctx.project_id == sample_project.id

    listed = await svc.list()
    assert len(listed) == 1
    assert listed[0].slug == "acme-corp"


@pytest.mark.asyncio
async def test_create_duplicate_slug_raises(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(DuplicateSlugError):
        await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)


@pytest.mark.asyncio
async def test_create_project_already_linked_raises(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(ProjectAlreadyLinkedError):
        await svc.create(slug="acme-second", project_id=sample_project.id, description=None)


@pytest.mark.asyncio
async def test_update_only_description(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description="old")
    updated = await svc.update(ctx.id, description="new")
    assert updated.description == "new"
    assert updated.slug == "acme-corp"


@pytest.mark.asyncio
async def test_update_rejects_slug_change(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    """Slug is immutable — the API must not expose a way to change it.
    Calling update with a slug kwarg raises SlugImmutableError."""
    svc = DevstackProjectContextService(db_session)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(SlugImmutableError):
        await svc.update(ctx.id, slug="renamed")


@pytest.mark.asyncio
async def test_delete(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    await svc.delete(ctx.id)
    assert await svc.list() == []


@pytest.mark.asyncio
async def test_get_by_slug(db_session: AsyncSession, sample_project: ProjectDB) -> None:
    svc = DevstackProjectContextService(db_session)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    ctx = await svc.get_by_slug("acme-corp")
    assert ctx is not None
    assert ctx.slug == "acme-corp"
    assert await svc.get_by_slug("missing") is None
