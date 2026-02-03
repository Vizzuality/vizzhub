"""Test configuration and fixtures."""

import csv
import os
from decimal import Decimal
from pathlib import Path

# CRITICAL: Set test environment variables BEFORE any app imports
# This ensures the settings object is initialized with test values
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-for-testing")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test"
)

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import ScoringConfig, set_scoring_config
from app.database import Base, get_db
from app.main import app

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
    from app.api import projects, metrics, collectors, scores, config, oauth, capture
    from app.api.deps import limiter as deps_limiter

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
