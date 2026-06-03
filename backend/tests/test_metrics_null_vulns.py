"""NULL high_severity_vulns must survive DB -> API model (not coerce to 0)."""

from datetime import UTC, date, datetime
from uuid import UUID

from app.modules.scorecard.models.metrics import GitHubMetrics, MetricsDB, SnapshotType
from app.modules.scorecard.models.metrics.schemas import Metrics
from app.modules.scorecard.services.normalizers.indicators import IndicatorNormalizer

_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
_METRICS_ID = UUID("00000000-0000-0000-0000-000000000002")
_CREATED_AT = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)


def _metrics_db(**overrides) -> MetricsDB:
    base = dict(
        id=_METRICS_ID,
        project_id=_PROJECT_ID,
        created_at=_CREATED_AT,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_year=2026,
        period_month=1,
        snapshot_type=SnapshotType.CUMULATIVE.value,
        sev1_incident=False,
        total_merged_prs=5,
        prs_without_review=1,
    )
    base.update(overrides)
    return MetricsDB(**base)


def test_null_vulns_preserved_as_none() -> None:
    db = _metrics_db(high_severity_vulns=None, high_severity_vulns_total=None)
    metrics = Metrics.from_db(db)
    assert metrics.github_metrics is not None
    assert metrics.github_metrics.high_severity_vulns is None
    assert metrics.github_metrics.high_severity_vulns_total is None


def test_zero_vulns_stay_zero() -> None:
    db = _metrics_db(high_severity_vulns=0, high_severity_vulns_total=0)
    metrics = Metrics.from_db(db)
    assert metrics.github_metrics is not None
    assert metrics.github_metrics.high_severity_vulns == 0
    assert metrics.github_metrics.high_severity_vulns_total == 0


def test_normalizer_high_vulns_none_when_inaccessible() -> None:
    gh = GitHubMetrics(total_merged_prs=5, prs_without_review=1, high_severity_vulns=None)
    normalizer = IndicatorNormalizer()
    assert normalizer._get_high_vulns(gh) is None


def test_normalizer_high_vulns_zero_is_real_zero() -> None:
    gh = GitHubMetrics(total_merged_prs=5, prs_without_review=1, high_severity_vulns=0)
    normalizer = IndicatorNormalizer()
    assert normalizer._get_high_vulns(gh) == 0
