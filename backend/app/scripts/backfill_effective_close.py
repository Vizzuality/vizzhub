"""One-time backfill of a real close date into projects.finished_at.

Effective close = the month cumulative cost first reaches 95% of total cost
(trims stray residual reports logged long after the project effectively ended).
Written in place ONLY where finished_at is the migration default
(finished_at IS NULL OR finished_at = end_date), protecting VizzHub-captured
closes. Idempotent. Data-only (no schema change).

Run: uv run python -m app.scripts.backfill_effective_close
"""

import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker

logger = structlog.get_logger()

_BACKFILL_SQL = text(
    """
    WITH monthly AS (
        SELECT project_id, month, sum(cost) AS c FROM (
            SELECT rp.project_id, per.date AS month, rp.cost
            FROM report_parts rp
            JOIN reports r ON r.id = rp.report_id
            JOIN reporting_periods per ON per.id = r.reporting_period_id
            UNION ALL
            SELECT nsc.project_id, per2.date AS month, nsc.cost
            FROM non_staff_costs nsc
            JOIN reporting_periods per2 ON per2.id = nsc.reporting_period_id
        ) x
        GROUP BY project_id, month
    ),
    tot AS (SELECT project_id, sum(c) AS total FROM monthly GROUP BY project_id),
    cum AS (
        SELECT m.project_id, m.month,
               sum(m.c) OVER (PARTITION BY m.project_id ORDER BY m.month) AS running,
               t.total
        FROM monthly m JOIN tot t ON t.project_id = m.project_id
        WHERE t.total > 0
    ),
    close95 AS (
        SELECT project_id, min(month) AS d FROM cum WHERE running >= 0.95 * total
        GROUP BY project_id
    )
    UPDATE projects p
    SET finished_at = close95.d
    FROM close95
    WHERE p.id = close95.project_id
      AND p.status = 'finished' AND p.is_billable AND NOT p.is_absence
      AND (p.finished_at IS NULL OR p.finished_at = p.end_date)
    """
)


async def backfill_effective_close(db: AsyncSession) -> int:
    result = await db.execute(_BACKFILL_SQL)
    updated = result.rowcount
    logger.info("effective_close_backfilled", projects_updated=updated)
    return updated


async def main() -> None:
    async with async_session_maker() as db:
        await backfill_effective_close(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
