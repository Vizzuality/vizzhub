"""Global Metrics Service - Calculates averaged metrics across all projects."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig, get_scoring_config
from app.modules.scorecard.models.global_metrics import (
    GlobalIndicators,
    GlobalMetricsDB,
    GlobalScores,
    IndicatorValue,
    ScoreValue,
)
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.modules.scorecard.models.scores import FinalScore
from app.modules.scorecard.services.score_computation import ScoreComputationService


# Indicator fields to average (must match GlobalMetricsDB columns)
INDICATOR_FIELDS = [
    "spi",
    "cpi",
    "on_time_milestones",
    "defect_density",
    "escaped_rate",
    "mttr_hours",
    "governance_compliance",
    "lead_time_days",
    "deployment_frequency",
    "change_failure_rate",
    "commitment_reliability",
    "pr_review_ratio",
    "test_maturity",
    "arch_checklist",
    "high_vulns",
    "okr_impact",
    "pm_satisfaction",
    "client_satisfaction",
    "story_review_ratio",
    "strategic_impact",
]

# Score fields to average (must match GlobalMetricsDB columns)
SCORE_FIELDS = [
    "score",
    "p_time",
    "p_cost",
    "p_quality",
    "p_value",
    "p_satisfaction",
    "p_flow",
    "p_engineering",
    "p_risk",
]

# Map strategic_impact categories to numeric values for averaging
STRATEGIC_IMPACT_VALUES = {
    "low": 0.25,
    "medium": 0.55,
    "high": 0.80,
    "transformational": 1.0,
}


class GlobalMetricsService:
    """Service for calculating and storing global metrics averages."""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()
        self.score_service = ScoreComputationService(self.config)

    async def calculate_and_store(
        self,
        db: AsyncSession,
        year: int,
        month: int,
    ) -> GlobalMetricsDB:
        """Calculate global averages for a specific month and store in DB.

        For each project with metrics in this period:
        1. Compute indicators and scores using ScoreComputationService
        2. Average all indicators (only counting projects with data)
        3. Average all scores (only counting projects with data)
        4. Store/update in global_metrics table

        Args:
            db: Database session
            year: Period year
            month: Period month (1-12)

        Returns:
            GlobalMetricsDB record (created or updated)
        """
        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.period_year == year)
            .where(MetricsDB.period_month == month)
            .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
        )
        metrics_list = list(result.scalars().all())

        if not metrics_list:
            return await self._upsert_empty(db, year, month)

        all_indicators: list[IndicatorsCreate] = []
        all_scores: list[FinalScore] = []
        strategic_impacts: list[float] = []

        for metrics_db in metrics_list:
            metrics = MetricsCreate.from_db(metrics_db)
            indicators, scores = self.score_service.compute(
                metrics, sev1_incident=metrics_db.sev1_incident
            )
            all_indicators.append(indicators)
            all_scores.append(scores)

            if metrics_db.strategic_impact:
                impact_value = STRATEGIC_IMPACT_VALUES.get(
                    metrics_db.strategic_impact.lower()
                )
                if impact_value is not None:
                    strategic_impacts.append(impact_value)

        averaged_indicators = self._average_indicators(all_indicators, strategic_impacts)
        averaged_scores = self._average_scores(all_scores)

        return await self._upsert(
            db, year, month, len(metrics_list), averaged_indicators, averaged_scores
        )

    def _average_indicators(
        self,
        indicators_list: list[IndicatorsCreate],
        strategic_impacts: list[float],
    ) -> GlobalIndicators:
        """Calculate average for each indicator, tracking count of non-null values."""
        result = {}

        for field in INDICATOR_FIELDS:
            if field == "strategic_impact":
                result[field] = IndicatorValue(
                    value=sum(strategic_impacts) / len(strategic_impacts)
                    if strategic_impacts
                    else None,
                    count=len(strategic_impacts),
                )
            else:
                values = [
                    getattr(ind, field)
                    for ind in indicators_list
                    if getattr(ind, field, None) is not None
                ]
                result[field] = IndicatorValue(
                    value=sum(values) / len(values) if values else None,
                    count=len(values),
                )

        return GlobalIndicators(**result)

    def _average_scores(self, scores_list: list[FinalScore]) -> GlobalScores:
        """Calculate average for each score dimension, tracking count of non-null values."""
        result = {}

        for field in SCORE_FIELDS:
            if field == "score":
                values = [s.score for s in scores_list if s.score is not None]
            else:
                values = [
                    getattr(s.dimensions, field)
                    for s in scores_list
                    if getattr(s.dimensions, field, None) is not None
                ]

            result[field] = ScoreValue(
                value=sum(values) / len(values) if values else None,
                count=len(values),
            )

        return GlobalScores(**result)

    async def _upsert_empty(
        self,
        db: AsyncSession,
        year: int,
        month: int,
    ) -> GlobalMetricsDB:
        """Create or update with empty data (no projects with metrics)."""
        return await self._upsert(
            db, year, month, 0, GlobalIndicators(), GlobalScores()
        )

    async def _upsert(
        self,
        db: AsyncSession,
        year: int,
        month: int,
        project_count: int,
        indicators: GlobalIndicators,
        scores: GlobalScores,
    ) -> GlobalMetricsDB:
        """Insert or update global metrics for a period."""
        result = await db.execute(
            select(GlobalMetricsDB)
            .where(GlobalMetricsDB.period_year == year)
            .where(GlobalMetricsDB.period_month == month)
        )
        existing = result.scalar_one_or_none()

        db_data = self._build_db_data(project_count, indicators, scores)

        if existing:
            for key, value in db_data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            record = existing
        else:
            record = GlobalMetricsDB(
                period_year=year,
                period_month=month,
                **db_data,
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    def _build_db_data(
        self,
        project_count: int,
        indicators: GlobalIndicators,
        scores: GlobalScores,
    ) -> dict:
        """Build dictionary of DB column values from indicators and scores."""
        data = {"project_count": project_count}

        for field in INDICATOR_FIELDS:
            ind_value: IndicatorValue = getattr(indicators, field)
            data[field] = ind_value.value
            data[f"{field}_count"] = ind_value.count

        for field in SCORE_FIELDS:
            score_value: ScoreValue = getattr(scores, field)
            data[field] = score_value.value
            data[f"{field}_count"] = score_value.count

        return data

    async def calculate_batch(
        self,
        db: AsyncSession,
        from_year: int,
        from_month: int,
        to_year: int,
        to_month: int,
    ) -> list[GlobalMetricsDB]:
        """Calculate global metrics for a range of months.

        Args:
            db: Database session
            from_year: Start year
            from_month: Start month (1-12)
            to_year: End year
            to_month: End month (1-12)

        Returns:
            List of GlobalMetricsDB records created/updated
        """
        records = []

        year, month = from_year, from_month
        while (year, month) <= (to_year, to_month):
            record = await self.calculate_and_store(db, year, month)
            records.append(record)

            month += 1
            if month > 12:
                month = 1
                year += 1

        return records

    async def get_record(
        self,
        db: AsyncSession,
        year: int,
        month: int,
    ) -> GlobalMetricsDB | None:
        """Get stored global metrics for a specific month."""
        result = await db.execute(
            select(GlobalMetricsDB)
            .where(GlobalMetricsDB.period_year == year)
            .where(GlobalMetricsDB.period_month == month)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        db: AsyncSession,
        limit: int = 12,
    ) -> list[GlobalMetricsDB]:
        """Get historical global metrics for trend display."""
        result = await db.execute(
            select(GlobalMetricsDB)
            .order_by(
                GlobalMetricsDB.period_year.desc(),
                GlobalMetricsDB.period_month.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_available_months(
        self,
        db: AsyncSession,
    ) -> list[tuple[int, int]]:
        """Get list of months that have stored global metrics."""
        result = await db.execute(
            select(GlobalMetricsDB.period_year, GlobalMetricsDB.period_month)
            .order_by(
                GlobalMetricsDB.period_year.desc(),
                GlobalMetricsDB.period_month.desc(),
            )
        )
        return [(row.period_year, row.period_month) for row in result.all()]
