"""Shared fixtures for integration tests."""

import pytest_asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB
from app.config import ScoringConfig


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, scoring_config: ScoringConfig) -> ProjectDB:
    """Create a test project."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Integration Test Project",
        jira_project_key="ITP",
        github_repo="test/integration-test",
        start_date=date.today() - timedelta(days=90),
        end_date=date.today() + timedelta(days=90),
        status="live",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_project_with_metrics(
    db_session: AsyncSession, test_project: ProjectDB
) -> tuple[ProjectDB, MetricsDB]:
    """Create a test project with complete metrics."""
    today = date.today()
    metrics = MetricsDB(
        project_id=str(test_project.id),
        period_start=today - timedelta(days=30),
        period_end=today,
        period_year=today.year,
        period_month=today.month,
        snapshot_type="cumulative",
        # EVM data (normalized columns)
        budget_total=Decimal("100000.0"),
        cost_to_date=Decimal("45000.0"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        # Milestones (JSON)
        milestones=[
            {
                "name": "Milestone 1",
                "planned_date": str(date.today() - timedelta(days=10)),
                "actual_date": str(date.today() - timedelta(days=10)),
            }
        ],
        # Defect metrics (normalized columns)
        bugs_total=5,
        tasks_completed=100,
        escaped_defects=1,
        mttr_hours=Decimal("24.0"),
        incidents_count=1,
        post_contract_tasks=0,
        # Flow metrics (normalized columns)
        lead_time_days=Decimal("3.0"),
        commitment_reliability=Decimal("0.9"),
        total_stories=50,
        stories_with_reviewer=45,
        # GitHub metrics (normalized columns)
        total_merged_prs=100,
        prs_without_review=5,
        high_severity_vulns=0,
        pr_size_median=Decimal("150.0"),
        review_turnaround_hours=Decimal("12.0"),
        deployment_frequency=Decimal("1.0"),
        change_failure_rate=Decimal("0.05"),
        # JSON fields
        test_maturity={
            "e2e": 4,
            "unit": 4,
            "accessibility": 3,
            "security": 4,
            "frontend": 4,
        },
        architecture={
            "docs_up_to_date": True,
            "iac_implemented": True,
            "adrs_maintained": True,
            "diagrams_updated": True,
        },
        pm_satisfaction={
            "delivery_complaints": "no",
            "design_complaints": "no",
            "overall_estimation": 4,
        },
        governance_exceptions=1,
        sev1_incident=False,
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(metrics)
    return test_project, metrics
