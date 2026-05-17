"""Test configuration and fixtures."""

import asyncio
import os
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse


def _worker_database_url(base_url: str, worker_id: str) -> str:
    """Append worker suffix to the DB name in a SQLAlchemy URL."""
    parsed = urlparse(base_url)
    new_path = f"{parsed.path}_{worker_id}"
    return urlunparse(parsed._replace(path=new_path))


def _ensure_worker_database(worker_db_url: str) -> None:
    """Create the worker-specific Postgres DB if it doesn't already exist."""
    import asyncpg

    parsed = urlparse(worker_db_url.replace("postgresql+asyncpg", "postgresql"))
    db_name = parsed.path.lstrip("/")
    admin_url = urlunparse(parsed._replace(path="/postgres"))

    async def _create() -> None:
        conn = await asyncpg.connect(admin_url)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()

    asyncio.run(_create())


# Each pytest-xdist worker gets its own Postgres database so parallel runs
# don't trip over the per-test drop_all/create_all on shared tables. The same
# URL is exported as both DATABASE_URL (read by app settings, used by code paths
# that build their own engine, e.g. oauth_service) and TEST_DATABASE_URL.
_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "main")
_BASE_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test",
)
_TEST_DB_URL = _worker_database_url(_BASE_DB_URL, _WORKER_ID)
_ensure_worker_database(_TEST_DB_URL)

# CRITICAL: Set test environment variables BEFORE any app imports
# This ensures the settings object is initialized with test values
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-for-testing")
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["TEST_DATABASE_URL"] = _TEST_DB_URL

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

TEST_DATABASE_URL = _TEST_DB_URL


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    """Provide a Fernet encryption key for all tests."""
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = _TEST_ENCRYPTION_KEY
        yield


_TEST_CONFIG_DEFAULTS: dict[str, Decimal] = {
    "target_defect_density": Decimal("6"),
    "target_escaped_rate": Decimal("3"),
    "target_mttr_hours": Decimal("24"),
    "target_spi": Decimal("0.8"),
    "target_cpi": Decimal("0.8"),
    "target_milestones_on_time": Decimal("85"),
    "target_lead_time_days": Decimal("10"),
    "target_high_vuln_count": Decimal("5"),
    "target_gov_exceptions": Decimal("3"),
    "target_pr_no_review_ratio": Decimal("10"),
    "target_pr_size_lines": Decimal("400"),
    "target_review_turnaround_hours": Decimal("24"),
    "target_deployment_frequency": Decimal("1"),
    "target_change_failure_rate": Decimal("15"),
    "target_post_contract_tasks": Decimal("3"),
    "target_test_maturity": Decimal("60"),
    "target_architecture": Decimal("80"),
    "target_pm_satisfaction": Decimal("85"),
    "target_client_satisfaction": Decimal("85"),
    "target_story_review_ratio": Decimal("85"),
    "target_commitment_reliability": Decimal("80"),
    "target_cost_variance": Decimal("0.10"),
    "target_governance_compliance": Decimal("80"),
    "target_okr_impact": Decimal("70"),
    "ideal_spi": Decimal("1.0"),
    "ideal_cpi": Decimal("1.0"),
    "weight_global_time": Decimal("0.12"),
    "weight_global_cost": Decimal("0.10"),
    "weight_global_quality": Decimal("0.205"),
    "weight_global_value": Decimal("0.05"),
    "weight_global_satisfaction": Decimal("0.12"),
    "weight_global_flow": Decimal("0.15"),
    "weight_global_engineering": Decimal("0.205"),
    "weight_global_risk": Decimal("0.05"),
    "weight_time_spi": Decimal("0.60"),
    "weight_time_milestones": Decimal("0.40"),
    "weight_cost_cpi": Decimal("0.70"),
    "weight_cost_variance": Decimal("0.30"),
    "weight_quality_defect_density": Decimal("0.05"),
    "weight_quality_escaped_rate": Decimal("0.15"),
    "weight_quality_mttr": Decimal("0.05"),
    "weight_quality_story_review": Decimal("0.25"),
    "weight_quality_governance": Decimal("0.20"),
    "weight_quality_pr_review": Decimal("0.10"),
    "weight_quality_change_failure_rate": Decimal("0.15"),
    "weight_quality_post_contract_tasks": Decimal("0.05"),
    "weight_value_okr_impact": Decimal("1.00"),
    "weight_satisfaction_client_survey": Decimal("0.90"),
    "weight_satisfaction_pm_estimation": Decimal("0.10"),
    "weight_survey_understanding": Decimal("0.12"),
    "weight_survey_proactivity": Decimal("0.12"),
    "weight_survey_communication": Decimal("0.10"),
    "weight_survey_time": Decimal("0.14"),
    "weight_survey_response": Decimal("0.10"),
    "weight_survey_quality": Decimal("0.24"),
    "weight_survey_expectations": Decimal("0.12"),
    "weight_survey_recommend": Decimal("0.06"),
    "weight_flow_lead_time": Decimal("0.35"),
    "weight_flow_commitment_reliability": Decimal("0.25"),
    "weight_flow_pr_size": Decimal("0.15"),
    "weight_flow_review_turnaround": Decimal("0.10"),
    "weight_flow_deployment_frequency": Decimal("0.15"),
    "weight_engineering_test_maturity": Decimal("0.50"),
    "weight_engineering_pr_review": Decimal("0.20"),
    "weight_engineering_architecture": Decimal("0.30"),
    "weight_risk_pr_no_review": Decimal("0.50"),
    "weight_risk_high_vulns": Decimal("0.50"),
    "weight_test_e2e": Decimal("0.40"),
    "weight_test_unit": Decimal("0.10"),
    "weight_test_accessibility": Decimal("0.10"),
    "weight_test_security": Decimal("0.20"),
    "weight_test_frontend": Decimal("0.20"),
    "const_sev1_cap": Decimal("60"),
    "const_grace_days": Decimal("3"),
    "const_threshold_green": Decimal("80"),
    "const_threshold_yellow": Decimal("60"),
}


def load_config_from_csv() -> dict[str, Decimal]:
    """Return the test scoring config defaults (name kept for backward compat)."""
    return dict(_TEST_CONFIG_DEFAULTS)


@pytest.fixture(scope="session")
def scoring_config() -> ScoringConfig:
    """Create a ScoringConfig loaded from CSV for testing."""
    config_dict = load_config_from_csv()
    config = ScoringConfig(config_dict)
    set_scoring_config(config)
    return config


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate limiter state before each test
    # Each API router has its own limiter instance that needs to be reset
    from app.core.api import oauth
    from app.core.api import projects_v2 as projects
    from app.core.api.deps import limiter as deps_limiter
    from app.main import limiter as main_limiter
    from app.modules.scorecard.api import capture, collectors, config, metrics, scores

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

    # Endpoints like /health/ready and load_scoring_config_from_db build sessions
    # from app.database.async_session_maker directly, bypassing the get_db override.
    # Connections in that pool are bound to this test's event loop, which
    # pytest-asyncio closes between tests; reusing them next test triggers
    # asyncpg "another operation in progress". Drain the pool so the next test
    # starts with fresh connections.
    from app.database import engine as app_engine

    await app_engine.dispose()


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
