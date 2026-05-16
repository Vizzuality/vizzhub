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
import mcp_server.models.command  # noqa: F401 — registers CommandDB to Base.metadata
from app.database import Base

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = _TEST_ENCRYPTION_KEY
        yield


@pytest.fixture(autouse=True, scope="session")
def _load_scoring_config_singleton():
    """Populate the ScoringConfig singleton for MCP scorecard tools.

    The backend test suite seeds this via its own `scoring_config` fixture
    (`backend/tests/conftest.py:170`). MCP tests run with their own conftest
    and never trigger that fixture, so `_ensure_scoring_config` falls
    through to an empty `ConfigParameter` table and every dimension weight
    resolves to 0 — making `FinalScore.score` collapse to None on otherwise
    well-populated metrics. Mirror the backend defaults here so MCP tests
    exercise the real calculator path.
    """
    from decimal import Decimal

    from app.config import ScoringConfig, set_scoring_config

    defaults: dict[str, Decimal] = {
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
        "const_sev1_cap": Decimal("60"),
        "const_grace_days": Decimal("3"),
        "const_threshold_green": Decimal("80"),
        "const_threshold_yellow": Decimal("60"),
    }
    set_scoring_config(ScoringConfig(defaults))


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


@pytest.fixture
def restricted_user():
    """A non-admin user with read-only permissions on a single module.

    Use in gate-regression tests: any write tool called under this context
    must raise ToolError. If a test passes with restricted_user, then someone
    removed the @mcp_requires decorator (or its permission string drifted).
    """
    from mcp_server.data.base import McpUserContext

    return McpUserContext(
        user_id="restricted-uuid",
        email="restricted@vizzuality.com",
        roles=["user"],
        permissions=["tracker:view"],
    )
