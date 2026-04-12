"""Shared test fixtures for MCP server tests."""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-for-testing")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test",
)

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.main  # noqa: F401 — registers all SQLAlchemy models to Base.metadata
from app.database import Base

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = _TEST_ENCRYPTION_KEY
        yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def use_test_db(db_session: AsyncSession):
    """Ensure all MCP tools use the test DB session and have admin context."""
    from mcp_server.data.base import FULL_ACCESS, override_mcp_user, override_session

    async with override_session(db_session):
        async with override_mcp_user(FULL_ACCESS):
            yield
