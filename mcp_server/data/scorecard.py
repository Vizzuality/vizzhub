"""Scorecard data access — project scores, scorecards, history, global metrics."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig, get_scoring_config
from app.core.models.project import ProjectDB
from app.modules.scorecard.models.global_metrics import GlobalMetricsDB
from app.modules.scorecard.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.modules.scorecard.services.score_computation import ScoreComputationService


async def _ensure_scoring_config(session: AsyncSession) -> ScoringConfig:
    """Get scoring config, loading from DB via the given session if needed.

    In HTTP mode the config is pre-loaded at FastAPI startup.
    In stdio mode or tests, load from DB on first use.
    """
    config = get_scoring_config()
    if config._config:
        return config

    from app.modules.scorecard.models.config import ConfigParameter

    result = await session.execute(select(ConfigParameter))
    params = result.scalars().all()
    config_dict = {p.name: p.value for p in params}
    config.load_from_dict(config_dict)
    return config


def _consolidate_metrics(metrics_list: list[MetricsDB]) -> MetricsDB:
    """Consolidate multiple metrics for the same period, taking first non-null."""
    if len(metrics_list) == 1:
        return metrics_list[0]

    from sqlalchemy import inspect as sa_inspect

    exclude = frozenset({
        "id", "project_id", "period_start", "period_end",
        "period_year", "period_month", "snapshot_type",
        "weights_applied", "targets_applied", "created_at", "sev1_incident",
    })

    base = metrics_list[0]
    mapper = sa_inspect(MetricsDB)
    fields = [col.key for col in mapper.columns if col.key not in exclude]

    for field in fields:
        if getattr(base, field) is None:
            for m in metrics_list[1:]:
                value = getattr(m, field)
                if value is not None:
                    setattr(base, field, value)
                    break

    if not base.sev1_incident:
        base.sev1_incident = any(m.sev1_incident for m in metrics_list[1:])

    return base


def _score_to_dict(indicators, scores) -> dict:
    """Convert indicators + scores to a flat dict for MCP output."""
    dims = scores.dimensions
    result = {
        "score": scores.score,
        "dimensions": {
            "time": dims.p_time,
            "cost": dims.p_cost,
            "quality": dims.p_quality,
            "value": dims.p_value,
            "satisfaction": dims.p_satisfaction,
            "flow": dims.p_flow,
            "engineering": dims.p_engineering,
            "risk": dims.p_risk,
        },
    }
    if scores.dora and scores.dora.score is not None:
        result["dora"] = {
            "score": scores.dora.score,
            "classification": scores.dora.classification,
        }
    return result


# ---------------------------------------------------------------------------
# 1. scorecard_get_project_scores
# ---------------------------------------------------------------------------

async def get_project_scores(
    session: AsyncSession,
    status: str | None = None,
) -> list[dict]:
    """All projects with their latest cumulative scores."""
    config = await _ensure_scoring_config(session)

    stmt = (
        select(ProjectDB.id, ProjectDB.name, ProjectDB.code, ProjectDB.status)
        .where(ProjectDB.is_absence.is_(False))
        .where(ProjectDB.has_scorecard.is_(True))
        .order_by(ProjectDB.name)
    )
    if status is not None:
        stmt = stmt.where(ProjectDB.status == status)

    projects = (await session.execute(stmt)).all()
    if not projects:
        return []

    score_service = ScoreComputationService(config)
    results = []

    for p in projects:
        metrics_result = await session.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == p.id)
            .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
            .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
            .limit(20)
        )
        metrics_list = list(metrics_result.scalars().all())
        if not metrics_list:
            results.append({
                "id": str(p.id),
                "name": p.name,
                "code": p.code,
                "status": p.status,
                "period": None,
                "score": None,
                "dimensions": None,
            })
            continue

        latest_end = metrics_list[0].period_end
        same_period = [m for m in metrics_list if m.period_end == latest_end]
        consolidated = _consolidate_metrics(same_period)
        metrics = MetricsCreate.from_db(consolidated)
        indicators, scores = score_service.compute(metrics, sev1_incident=consolidated.sev1_incident)

        entry = {
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "status": p.status,
            "period": f"{consolidated.period_year}-{consolidated.period_month:02d}",
        }
        entry.update(_score_to_dict(indicators, scores))
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# 2. scorecard_get_project_scorecard
# ---------------------------------------------------------------------------

async def get_project_scorecard(
    session: AsyncSession,
    project_id: UUID,
    year: int | None = None,
    month: int | None = None,
) -> dict | None:
    """Full scorecard for a project: metrics, indicators, dimensions, DORA."""
    config = await _ensure_scoring_config(session)

    project = await session.get(ProjectDB, project_id)
    if project is None:
        return None

    if year is not None and month is not None:
        result = await session.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == project_id)
            .where(MetricsDB.period_year == year)
            .where(MetricsDB.period_month == month)
            .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
        )
        metrics_db = result.scalar_one_or_none()
        if metrics_db is None:
            return {"error": f"No metrics for {year}-{month:02d}"}
    else:
        result = await session.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == project_id)
            .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
            .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
            .limit(20)
        )
        metrics_list = list(result.scalars().all())
        if not metrics_list:
            return {"error": "No metrics found"}
        latest_end = metrics_list[0].period_end
        same_period = [m for m in metrics_list if m.period_end == latest_end]
        metrics_db = _consolidate_metrics(same_period)

    metrics = MetricsCreate.from_db(metrics_db)
    score_service = ScoreComputationService(config)
    indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)

    ind_dict = indicators.model_dump(exclude_none=True)
    dims = scores.dimensions

    scorecard: dict = {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "code": project.code,
            "status": project.status,
        },
        "period": f"{metrics_db.period_year}-{metrics_db.period_month:02d}",
        "score": scores.score,
        "dimensions": {
            "time": dims.p_time,
            "cost": dims.p_cost,
            "quality": dims.p_quality,
            "value": dims.p_value,
            "satisfaction": dims.p_satisfaction,
            "flow": dims.p_flow,
            "engineering": dims.p_engineering,
            "risk": dims.p_risk,
        },
        "indicators": ind_dict,
    }

    if scores.dora and scores.dora.score is not None:
        dora_detail = {}
        for name, detail in scores.dora.metrics.items():
            dora_detail[name] = {
                "value": detail.value,
                "level": detail.level,
                "score": detail.score,
            }
        scorecard["dora"] = {
            "score": scores.dora.score,
            "classification": scores.dora.classification,
            "metrics": dora_detail,
        }

    if metrics.evm_data:
        evm = metrics.evm_data
        scorecard["evm"] = {
            "budget_total": evm.budget_total,
            "cost_to_date": evm.cost_to_date,
            "percent_completed": evm.percent_completed,
            "percent_planned": evm.percent_planned,
        }

    if metrics.milestones:
        scorecard["milestones"] = [
            {
                "name": m.name,
                "planned_date": m.planned_date,
                "actual_date": m.actual_date,
            }
            for m in metrics.milestones
        ]

    return scorecard


# ---------------------------------------------------------------------------
# 3. scorecard_get_project_history
# ---------------------------------------------------------------------------

async def get_project_history(
    session: AsyncSession,
    project_id: UUID,
    limit: int = 12,
) -> list[dict] | None:
    """Score history for a project across periods."""
    project = await session.get(ProjectDB, project_id)
    if project is None:
        return None

    config = await _ensure_scoring_config(session)

    result = await session.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == project_id)
        .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
        .order_by(MetricsDB.period_year.desc(), MetricsDB.period_month.desc())
        .limit(limit)
    )
    metrics_list = list(result.scalars().all())
    if not metrics_list:
        return []

    score_service = ScoreComputationService(config)
    history = []
    for m_db in metrics_list:
        metrics = MetricsCreate.from_db(m_db)
        indicators, scores = score_service.compute(metrics, sev1_incident=m_db.sev1_incident)

        entry = {
            "period": f"{m_db.period_year}-{m_db.period_month:02d}",
        }
        entry.update(_score_to_dict(indicators, scores))

        key_indicators = {}
        ind = indicators
        for field in ("spi", "cpi", "lead_time_days", "commitment_reliability",
                      "defect_density", "test_maturity", "deployment_frequency"):
            val = getattr(ind, field, None)
            if val is not None:
                key_indicators[field] = round(val, 3)
        if key_indicators:
            entry["key_indicators"] = key_indicators

        history.append(entry)

    return history


# ---------------------------------------------------------------------------
# 4. scorecard_get_global_metrics
# ---------------------------------------------------------------------------

async def get_global_metrics(
    session: AsyncSession,
    limit: int = 12,
) -> list[dict]:
    """Organization-wide averaged scores across all projects."""
    result = await session.execute(
        select(GlobalMetricsDB)
        .order_by(GlobalMetricsDB.period_year.desc(), GlobalMetricsDB.period_month.desc())
        .limit(limit)
    )
    records = list(result.scalars().all())

    dimension_fields = [
        "score", "p_time", "p_cost", "p_quality", "p_value",
        "p_satisfaction", "p_flow", "p_engineering", "p_risk",
    ]
    indicator_fields = [
        "spi", "cpi", "lead_time_days", "commitment_reliability",
        "deployment_frequency", "change_failure_rate", "test_maturity",
        "defect_density", "client_satisfaction", "pm_satisfaction",
    ]

    rows = []
    for r in records:
        dims = {}
        for f in dimension_fields:
            val = getattr(r, f, None)
            count = getattr(r, f"{f}_count", None)
            if val is not None:
                dims[f] = {"value": round(val, 1), "projects": count or 0}

        inds = {}
        for f in indicator_fields:
            val = getattr(r, f, None)
            count = getattr(r, f"{f}_count", None)
            if val is not None:
                inds[f] = {"value": round(val, 3), "projects": count or 0}

        rows.append({
            "period": f"{r.period_year}-{r.period_month:02d}",
            "project_count": r.project_count,
            "scores": dims,
            "indicators": inds,
        })

    return rows
