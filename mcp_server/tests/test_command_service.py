"""Tests for command queue service."""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from mcp_server.models.command import CommandDB
from mcp_server.services.command_service import CommandService


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="test@vizzuality.com",
        name="Test User",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_command_model_create(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    cmd = CommandDB(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        requested_by=test_user.id,
    )
    db_session.add(cmd)
    await db_session.flush()
    await db_session.refresh(cmd)

    assert cmd.id is not None
    assert cmd.status == "pending"
    assert cmd.requested_at is not None
    assert cmd.reviewed_by is None


@pytest.mark.asyncio
async def test_enqueue_creates_pending_command(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )
    assert cmd.status == "pending"
    assert cmd.module == "iso_docs"
    assert cmd.action == "create_page"
    assert cmd.requested_by == test_user.id


@pytest.mark.asyncio
async def test_approve_transitions_to_executed(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )

    async def fake_executor(action, target, payload, user_id, session):
        return {"node_id": "fake-id", "slug": "new-policy"}

    result = await svc.approve(cmd.id, test_user.id, executor=fake_executor)
    assert result.status == "executed"
    assert result.result == {"node_id": "fake-id", "slug": "new-policy"}
    assert result.reviewed_by == test_user.id
    assert result.executed_at is not None


@pytest.mark.asyncio
async def test_approve_failed_execution(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )

    async def failing_executor(action, target, payload, user_id, session):
        raise ValueError("Registry type not found")

    result = await svc.approve(cmd.id, test_user.id, executor=failing_executor)
    assert result.status == "failed"
    assert "Registry type not found" in result.error


@pytest.mark.asyncio
async def test_reject_command(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )
    result = await svc.reject(cmd.id, test_user.id)
    assert result.status == "rejected"
    assert result.reviewed_by == test_user.id


@pytest.mark.asyncio
async def test_approve_non_pending_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "X"}, summary="X", user_id=test_user.id,
    )
    await svc.reject(cmd.id, test_user.id)

    async def noop(a, t, p, u, s):
        return {}

    with pytest.raises(ValueError, match="not pending"):
        await svc.approve(cmd.id, test_user.id, executor=noop)


@pytest.mark.asyncio
async def test_list_pending_filters_by_user(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    other = UserDB(email="other@vizzuality.com", name="Other")
    db_session.add(other)
    await db_session.flush()

    svc = CommandService(db_session)
    await svc.enqueue(
        module="iso_docs", action="create_page", target=None,
        payload={}, summary="User cmd", user_id=test_user.id,
    )
    await svc.enqueue(
        module="playbook", action="create_article", target=None,
        payload={}, summary="Other cmd", user_id=other.id,
    )

    mine = await svc.list_pending(user_id=test_user.id)
    assert len(mine) == 1
    assert mine[0].summary == "User cmd"

    all_pending = await svc.list_pending()
    assert len(all_pending) == 2


@pytest.mark.asyncio
async def test_list_pending_filters_by_module(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    await svc.enqueue(
        module="iso_docs", action="create_page", target=None,
        payload={}, summary="ISO cmd", user_id=test_user.id,
    )
    await svc.enqueue(
        module="playbook", action="create_article", target=None,
        payload={}, summary="PB cmd", user_id=test_user.id,
    )

    iso_only = await svc.list_pending(module="iso_docs")
    assert len(iso_only) == 1
    assert iso_only[0].module == "iso_docs"


@pytest.mark.asyncio
async def test_approve_nonexistent_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)

    async def noop(a, t, p, u, s):
        return {}

    with pytest.raises(ValueError, match="not found"):
        await svc.approve(uuid4(), test_user.id, executor=noop)


@pytest.mark.asyncio
async def test_enqueue_approved_sets_status_immediately(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue_approved(
        module="devstack",
        action="update_project_context",
        target="acme-corp",
        payload={"sha": "abc123"},
        summary="Update acme-corp CLAUDE.md",
        user_id=test_user.id,
    )
    assert cmd.status == "approved"
    assert cmd.reviewed_by == test_user.id
    assert cmd.reviewed_at is not None
