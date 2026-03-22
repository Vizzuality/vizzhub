"""Test configuration and fixtures."""

import csv
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

# CRITICAL: Set test environment variables BEFORE any app imports
# This ensures the settings object is initialized with test values
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-for-testing")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test",
)

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import ScoringConfig, set_scoring_config
from app.core.models.role import RoleDB, UserRoleDB
from app.database import Base, get_db
from app.main import app

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    """Provide a Fernet encryption key for all tests."""
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = _TEST_ENCRYPTION_KEY
        yield


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test",
)


def load_config_from_csv() -> dict[str, Decimal]:
    """Load config parameters from CSV seed file for testing."""
    csv_path = Path(__file__).parent.parent / "seeds" / "config_parameters.csv"
    config_dict = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            config_dict[row["name"]] = Decimal(row["value"])
    return config_dict


@pytest.fixture(scope="session")
def scoring_config() -> ScoringConfig:
    """Create a ScoringConfig loaded from CSV for testing."""
    config_dict = load_config_from_csv()
    config = ScoringConfig(config_dict)
    set_scoring_config(config)
    return config


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Ensure clean state: drop all tables first, then create
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    # Cleanup after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate limiter state before each test
    # Each API router has its own limiter instance that needs to be reset
    from app.main import limiter as main_limiter
    from app.core.api import projects_v2 as projects, oauth
    from app.modules.scorecard.api import metrics, collectors, scores, config, capture
    from app.core.api.deps import limiter as deps_limiter

    main_limiter.reset()
    projects.limiter.reset()
    metrics.limiter.reset()
    collectors.limiter.reset()
    scores.limiter.reset()
    config.limiter.reset()
    oauth.limiter.reset()
    capture.limiter.reset()
    deps_limiter.reset()  # Used by global_metrics, silences, and notifications

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def seed_roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    """Seed roles table for tests. Returns name->RoleDB mapping."""
    roles = {}
    for name in ("user", "manager", "admin"):
        role = RoleDB(name=name)
        db_session.add(role)
        roles[name] = role
    await db_session.flush()
    return roles


async def assign_roles(
    db_session: AsyncSession,
    user_id,
    role_ids: list,
) -> None:
    """Assign roles to a user in tests."""
    for role_id in role_ids:
        db_session.add(UserRoleDB(user_id=user_id, role_id=role_id))
    await db_session.flush()


@pytest.fixture
def mock_github_client():
    """Create a mock GitHubClient for testing GitHub collectors."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.validate_repo_slug.return_value = ("owner", "repo")
    return client


@pytest.fixture
def mock_jira_client():
    """Create a mock JiraClient for testing Jira collectors."""
    from unittest.mock import MagicMock

    client = MagicMock()
    return client
