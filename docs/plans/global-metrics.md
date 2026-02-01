# Plan: Global Metrics Dashboard

**Branch:** `feature/global-metrics`
**Status:** READY FOR IMPLEMENTATION

## Overview

Add a global metrics dashboard that displays averaged indicators and scores across all projects. Monthly records enable trend tracking and ISO reporting.

## Core Concept

- Calculate **monthly averages** from all projects' **cumulative** metrics
- Store in `global_metrics` table (same pattern as `metrics` table with period columns)
- Same KPIs as individual projects
- UI similar to ProjectDetail but simplified (no edit, no collectors)

---

## Phase 1: Backend - Database & Models

### 1.1 Create GlobalMetrics Model

**File:** `backend/app/models/global_metrics.py`

Following the same pattern as the `metrics` table - historical data stored with `period_year` and `period_month` columns, not a separate "snapshots" table.

```python
from sqlalchemy import Column, Integer, Float, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.database import Base

class GlobalMetricsDB(Base):
    """
    Stores averaged metrics across all projects for a given month.
    Follows the same pattern as MetricsDB with period-based storage.
    """
    __tablename__ = "global_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)

    # Metadata
    project_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Averaged Indicators (0-1 scale)
    spi = Column(Float, nullable=True)
    cpi = Column(Float, nullable=True)
    on_time_milestones = Column(Float, nullable=True)
    defect_density = Column(Float, nullable=True)
    escaped_rate = Column(Float, nullable=True)
    mttr_hours = Column(Float, nullable=True)
    governance_compliance = Column(Float, nullable=True)
    lead_time_days = Column(Float, nullable=True)
    deployment_frequency = Column(Float, nullable=True)
    change_failure_rate = Column(Float, nullable=True)
    commitment_reliability = Column(Float, nullable=True)
    pr_review_ratio = Column(Float, nullable=True)
    test_maturity = Column(Float, nullable=True)
    arch_checklist = Column(Float, nullable=True)
    high_vulns = Column(Float, nullable=True)
    okr_impact = Column(Float, nullable=True)
    pm_satisfaction = Column(Float, nullable=True)
    client_satisfaction = Column(Float, nullable=True)
    story_review_ratio = Column(Float, nullable=True)
    strategic_impact = Column(Float, nullable=True)  # Numeric average

    # Averaged Dimension Scores (0-100 scale)
    score = Column(Float, nullable=True)
    p_time = Column(Float, nullable=True)
    p_cost = Column(Float, nullable=True)
    p_quality = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    p_satisfaction = Column(Float, nullable=True)
    p_flow = Column(Float, nullable=True)
    p_engineering = Column(Float, nullable=True)
    p_risk = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint('period_year', 'period_month', name='uq_global_metrics_period'),
    )
```

### 1.2 Create Alembic Migration

```bash
cd backend
alembic revision --autogenerate -m "add global_metrics table"
alembic upgrade head
```

### 1.3 Add Pydantic Schemas

**File:** `backend/app/models/global_metrics.py` (add to same file)

```python
from pydantic import BaseModel
from datetime import datetime

class GlobalIndicators(BaseModel):
    spi: float | None = None
    cpi: float | None = None
    on_time_milestones: float | None = None
    defect_density: float | None = None
    escaped_rate: float | None = None
    mttr_hours: float | None = None
    governance_compliance: float | None = None
    lead_time_days: float | None = None
    deployment_frequency: float | None = None
    change_failure_rate: float | None = None
    commitment_reliability: float | None = None
    pr_review_ratio: float | None = None
    test_maturity: float | None = None
    arch_checklist: float | None = None
    high_vulns: float | None = None
    okr_impact: float | None = None
    pm_satisfaction: float | None = None
    client_satisfaction: float | None = None
    story_review_ratio: float | None = None
    strategic_impact: float | None = None

class GlobalScores(BaseModel):
    score: float | None = None
    p_time: float | None = None
    p_cost: float | None = None
    p_quality: float | None = None
    p_value: float | None = None
    p_satisfaction: float | None = None
    p_flow: float | None = None
    p_engineering: float | None = None
    p_risk: float | None = None

class GlobalMetricsResponse(BaseModel):
    period_year: int
    period_month: int
    project_count: int
    indicators: GlobalIndicators
    scores: GlobalScores

class GlobalMetricsRecord(GlobalMetricsResponse):
    """Response for a stored global metrics record."""
    id: str
    created_at: datetime
    updated_at: datetime

class GlobalMetricsHistoryResponse(BaseModel):
    """Response for historical global metrics query."""
    records: list[GlobalMetricsRecord]
```

### 1.4 Update models __init__.py

**File:** `backend/app/models/__init__.py`

Add exports for `GlobalMetricsDB` and Pydantic schemas.

---

## Phase 2: Backend - Calculation Service

### 2.1 Create GlobalMetricsService

**File:** `backend/app/services/global_metrics_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.metrics import MetricsDB
from app.models.global_metrics import (
    GlobalMetricsDB,
    GlobalIndicators,
    GlobalScores,
    GlobalMetricsResponse,
)
from app.services.scoring_config import ScoringConfig

INDICATOR_FIELDS = [
    'spi', 'cpi', 'on_time_milestones', 'defect_density', 'escaped_rate',
    'mttr_hours', 'governance_compliance', 'lead_time_days', 'deployment_frequency',
    'change_failure_rate', 'commitment_reliability', 'pr_review_ratio',
    'test_maturity', 'arch_checklist', 'high_vulns', 'okr_impact',
    'pm_satisfaction', 'client_satisfaction', 'story_review_ratio'
]

STRATEGIC_IMPACT_VALUES = {
    "LOW": 25,
    "MEDIUM": 55,
    "HIGH": 80,
    "TRANSFORMATIONAL": 100
}

class GlobalMetricsService:
    def __init__(self, config: ScoringConfig):
        self.config = config

    async def calculate_for_month(
        self,
        db: AsyncSession,
        year: int,
        month: int,
    ) -> GlobalMetricsResponse:
        """Calculate global averages for a specific month from all projects' cumulative metrics."""

        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.period_year == year)
            .where(MetricsDB.period_month == month)
            .where(MetricsDB.snapshot_type == "cumulative")
        )
        metrics_list = result.scalars().all()

        if not metrics_list:
            return GlobalMetricsResponse(
                period_year=year,
                period_month=month,
                project_count=0,
                indicators=GlobalIndicators(),
                scores=GlobalScores(),
            )

        indicators = self._average_indicators(metrics_list)
        scores = self._calculate_scores(indicators)

        return GlobalMetricsResponse(
            period_year=year,
            period_month=month,
            project_count=len(metrics_list),
            indicators=indicators,
            scores=scores,
        )

    def _average_indicators(self, metrics_list: list[MetricsDB]) -> GlobalIndicators:
        """Calculate average for each indicator, excluding nulls."""
        averages = {}

        for field in INDICATOR_FIELDS:
            values = [
                getattr(m, field)
                for m in metrics_list
                if getattr(m, field) is not None
            ]
            averages[field] = sum(values) / len(values) if values else None

        # Handle strategic_impact separately (category → numeric → average)
        impact_values = [
            STRATEGIC_IMPACT_VALUES.get(m.strategic_impact)
            for m in metrics_list
            if m.strategic_impact in STRATEGIC_IMPACT_VALUES
        ]
        averages['strategic_impact'] = (
            sum(impact_values) / len(impact_values) if impact_values else None
        )

        return GlobalIndicators(**averages)

    def _calculate_scores(self, indicators: GlobalIndicators) -> GlobalScores:
        """Calculate dimension scores from averaged indicators using existing calculators."""
        # Reuse existing dimension calculators with averaged indicator values
        # Each calculator takes normalized indicators and returns 0-100 score
        # TODO: Wire up existing calculators
        return GlobalScores()

    async def upsert(
        self,
        db: AsyncSession,
        metrics: GlobalMetricsResponse,
    ) -> GlobalMetricsDB:
        """Insert or update global metrics for a period (same pattern as MetricsService)."""
        result = await db.execute(
            select(GlobalMetricsDB)
            .where(GlobalMetricsDB.period_year == metrics.period_year)
            .where(GlobalMetricsDB.period_month == metrics.period_month)
        )
        existing = result.scalar_one_or_none()

        if existing:
            for key, value in metrics.indicators.model_dump().items():
                setattr(existing, key, value)
            for key, value in metrics.scores.model_dump().items():
                setattr(existing, key, value)
            existing.project_count = metrics.project_count
            record = existing
        else:
            record = GlobalMetricsDB(
                period_year=metrics.period_year,
                period_month=metrics.period_month,
                project_count=metrics.project_count,
                **metrics.indicators.model_dump(),
                **metrics.scores.model_dump(),
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

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
                GlobalMetricsDB.period_month.desc()
            )
            .limit(limit)
        )
        return result.scalars().all()
```

---

## Phase 3: Backend - API Endpoints

### 3.1 Create Global API Router

**File:** `backend/app/api/global_metrics.py`

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_db
from app.services.global_metrics_service import GlobalMetricsService
from app.services.scoring_config import ScoringConfig
from app.models.global_metrics import (
    GlobalMetricsResponse,
    GlobalMetricsRecord,
    GlobalMetricsHistoryResponse,
)

router = APIRouter(prefix="/api/global", tags=["global"])

def get_global_service() -> GlobalMetricsService:
    config = ScoringConfig()
    return GlobalMetricsService(config)

@router.get("/current", response_model=GlobalMetricsResponse)
async def get_current_global_metrics(
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Calculate global metrics for current month (on-the-fly, not stored)."""
    now = datetime.now()
    return await service.calculate_for_month(db, now.year, now.month)

@router.get("/calculate", response_model=GlobalMetricsResponse)
async def calculate_global_metrics(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Calculate global metrics for a specific month (on-the-fly, not stored)."""
    return await service.calculate_for_month(db, year, month)

@router.post("/capture", response_model=GlobalMetricsRecord)
async def capture_global_metrics(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Calculate and store global metrics for a specific month (upsert)."""
    metrics = await service.calculate_for_month(db, year, month)
    record = await service.upsert(db, metrics)
    return record

@router.get("/history", response_model=GlobalMetricsHistoryResponse)
async def get_global_metrics_history(
    limit: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Get historical global metrics for trend display."""
    records = await service.get_history(db, limit)
    return GlobalMetricsHistoryResponse(records=records)

@router.get("/export")
async def export_global_metrics(
    year: int = Query(...),
    format: str = Query("csv", regex="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Export global metrics for ISO reporting."""
    # TODO: Implement CSV/JSON export
    pass
```

### 3.2 Register Router in Main

**File:** `backend/app/main.py`

```python
from app.api.global_metrics import router as global_router
app.include_router(global_router)
```

---

## Phase 4: Frontend - Types & Hooks

### 4.1 Add Types

**File:** `frontend/src/types/global.ts`

```typescript
export interface GlobalIndicators {
  spi: number | null;
  cpi: number | null;
  on_time_milestones: number | null;
  defect_density: number | null;
  escaped_rate: number | null;
  mttr_hours: number | null;
  governance_compliance: number | null;
  lead_time_days: number | null;
  deployment_frequency: number | null;
  change_failure_rate: number | null;
  commitment_reliability: number | null;
  pr_review_ratio: number | null;
  test_maturity: number | null;
  arch_checklist: number | null;
  high_vulns: number | null;
  okr_impact: number | null;
  pm_satisfaction: number | null;
  client_satisfaction: number | null;
  story_review_ratio: number | null;
  strategic_impact: number | null;
}

export interface GlobalScores {
  score: number | null;
  p_time: number | null;
  p_cost: number | null;
  p_quality: number | null;
  p_value: number | null;
  p_satisfaction: number | null;
  p_flow: number | null;
  p_engineering: number | null;
  p_risk: number | null;
}

export interface GlobalMetrics {
  period_year: number;
  period_month: number;
  project_count: number;
  indicators: GlobalIndicators;
  scores: GlobalScores;
}

export interface GlobalMetricsRecord extends GlobalMetrics {
  id: string;
  created_at: string;
  updated_at: string;
}
```

### 4.2 Add Query Keys

**File:** `frontend/src/hooks/queryKeys.ts`

```typescript
// Add to existing queryKeys
global: {
  current: ['global', 'current'] as const,
  calculate: (year: number, month: number) =>
    ['global', 'calculate', year, month] as const,
  history: (limit?: number) =>
    ['global', 'history', limit] as const,
},
```

### 4.3 Create Hooks

**File:** `frontend/src/hooks/useGlobalMetrics.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { queryKeys } from './queryKeys';
import type { GlobalMetrics, GlobalMetricsRecord } from '../types/global';

export function useCurrentGlobalMetrics() {
  return useQuery({
    queryKey: queryKeys.global.current,
    queryFn: async (): Promise<GlobalMetrics> => {
      const response = await api.get('/api/global/current');
      return response.data;
    },
  });
}

export function useGlobalMetrics(year: number, month: number) {
  return useQuery({
    queryKey: queryKeys.global.calculate(year, month),
    queryFn: async (): Promise<GlobalMetrics> => {
      const response = await api.get('/api/global/calculate', {
        params: { year, month },
      });
      return response.data;
    },
  });
}

export function useGlobalMetricsHistory(limit = 12) {
  return useQuery({
    queryKey: queryKeys.global.history(limit),
    queryFn: async (): Promise<GlobalMetricsRecord[]> => {
      const response = await api.get('/api/global/history', {
        params: { limit },
      });
      return response.data.records;
    },
  });
}

export function useCaptureGlobalMetrics() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ year, month }: { year: number; month: number }) => {
      const response = await api.post('/api/global/capture', null, {
        params: { year, month },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['global'] });
    },
  });
}
```

---

## Phase 5: Frontend - Global Dashboard Page

### 5.1 Create Page Component

**File:** `frontend/src/pages/GlobalDashboard.tsx`

```typescript
import { useState } from 'react';
import { useCurrentGlobalMetrics, useGlobalMetricsHistory } from '../hooks/useGlobalMetrics';
import { useConfigParameters } from '../hooks/useConfig';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import { ALL_DIMENSIONS, type Dimension } from '../types';

export default function GlobalDashboard(): JSX.Element {
  const [visibleDimensions, setVisibleDimensions] = useState<Set<Dimension>>(
    new Set(ALL_DIMENSIONS)
  );

  const { data: globalMetrics, isLoading, error } = useCurrentGlobalMetrics();
  const { data: history } = useGlobalMetricsHistory(12);
  const { data: config } = useConfigParameters();

  const handleToggleDimension = (dimension: Dimension) => {
    setVisibleDimensions((prev) => {
      const next = new Set(prev);
      if (next.has(dimension)) {
        next.delete(dimension);
      } else {
        next.add(dimension);
      }
      return next;
    });
  };

  const handleResetFilters = () => {
    setVisibleDimensions(new Set(ALL_DIMENSIONS));
  };

  const getTarget = (name: string): number | null => {
    const targets = config?.['Targets'];
    if (!targets) return null;
    const param = targets.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error || !globalMetrics) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading global metrics
          </p>
        </CardContent>
      </Card>
    );
  }

  // Transform to ScoreCard expected format
  const scoreData = {
    score: globalMetrics.scores.score ?? 0,
    dimensions: {
      p_time: globalMetrics.scores.p_time ?? 0,
      p_cost: globalMetrics.scores.p_cost ?? 0,
      p_quality: globalMetrics.scores.p_quality ?? 0,
      p_value: globalMetrics.scores.p_value ?? 0,
      p_satisfaction: globalMetrics.scores.p_satisfaction ?? 0,
      p_flow: globalMetrics.scores.p_flow ?? 0,
      p_engineering: globalMetrics.scores.p_engineering ?? 0,
      p_risk: globalMetrics.scores.p_risk ?? 0,
    },
    weights_applied: {},
    dora: null,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Global Metrics</h1>
        <p className="text-muted-foreground mt-1">
          Averaged across {globalMetrics.project_count} projects
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScoreCard
          score={scoreData}
          snapshots={history}
          visibleDimensions={visibleDimensions}
          onToggleDimension={handleToggleDimension}
          onResetFilters={handleResetFilters}
        />
        <DimensionChart
          scores={scoreData.dimensions}
          snapshots={history}
          visibleDimensions={visibleDimensions}
          onToggleDimension={handleToggleDimension}
        />
      </div>

      <Separator className="my-6" />

      {/* Sub-indicators by dimension */}
      {/* Similar to ProjectDetail but using globalMetrics.indicators */}
      {/* TODO: Add SubIndicatorCard grid for each dimension */}
    </div>
  );
}
```

### 5.2 Add Route

**File:** `frontend/src/App.tsx`

```typescript
import GlobalDashboard from './pages/GlobalDashboard';

// Add to routes
<Route path="/global" element={<GlobalDashboard />} />
```

### 5.3 Add Navigation Link

**File:** `frontend/src/components/layout/Sidebar.tsx` (or equivalent)

```typescript
// Add link to /global in navigation
<NavLink to="/global">Global Metrics</NavLink>
```

---

## Phase 6: Testing

### 6.1 Backend Tests

**File:** `backend/tests/test_global_metrics.py`

```python
import pytest
from app.services.global_metrics_service import GlobalMetricsService

class TestGlobalMetricsService:
    def test_average_indicators_excludes_nulls(self):
        # Test that null values don't affect average
        pass

    def test_average_indicators_empty_list(self):
        # Test with no metrics returns empty response
        pass

    def test_strategic_impact_conversion(self):
        # Test category to numeric conversion for averaging
        pass

    def test_calculate_scores_from_indicators(self):
        # Test score calculation
        pass

    def test_upsert_creates_new_record(self):
        # Test insert when no record exists
        pass

    def test_upsert_updates_existing_record(self):
        # Test update when record exists for period
        pass

class TestGlobalAPI:
    async def test_get_current_metrics(self, client):
        pass

    async def test_capture_metrics(self, client):
        pass

    async def test_get_history(self, client):
        pass
```

### 6.2 Frontend Tests

**File:** `frontend/src/pages/__tests__/GlobalDashboard.test.tsx`

```typescript
describe('GlobalDashboard', () => {
  it('renders loading state', () => {});
  it('renders error state', () => {});
  it('displays project count', () => {});
  it('renders score cards', () => {});
  it('renders dimension chart', () => {});
});
```

---

## Implementation Order

1. **Phase 1**: Database model & migration
2. **Phase 2**: Calculation service (core logic)
3. **Phase 3**: API endpoints
4. **Phase 4**: Frontend types & hooks
5. **Phase 5**: Global dashboard page
6. **Phase 6**: Tests

## Files to Create/Modify

| File | Action |
|------|--------|
| `backend/app/models/global_metrics.py` | CREATE |
| `backend/alembic/versions/xxx_add_global_metrics.py` | CREATE (auto) |
| `backend/app/models/__init__.py` | MODIFY |
| `backend/app/services/global_metrics_service.py` | CREATE |
| `backend/app/api/global_metrics.py` | CREATE |
| `backend/app/main.py` | MODIFY |
| `backend/tests/test_global_metrics.py` | CREATE |
| `frontend/src/types/global.ts` | CREATE |
| `frontend/src/hooks/queryKeys.ts` | MODIFY |
| `frontend/src/hooks/useGlobalMetrics.ts` | CREATE |
| `frontend/src/pages/GlobalDashboard.tsx` | CREATE |
| `frontend/src/pages/__tests__/GlobalDashboard.test.tsx` | CREATE |
| `frontend/src/App.tsx` | MODIFY |

## Key Simplifications

Following the existing `metrics` table pattern:
- **No separate "snapshots" table** - `global_metrics` stores historical data with `period_year`/`period_month`
- **Upsert pattern** - same period overwrites previous record (like project metrics)
- **Reuse existing calculators** - averaged indicators go through same scoring logic
- **Same API patterns** - `/current` (on-the-fly), `/capture` (store), `/history` (trend data)

## Verification

1. Run backend tests: `pytest tests/test_global_metrics.py`
2. Run frontend tests: `npm test`
3. Manual test: Navigate to `/global`, verify data displays
4. Verify capture and trend chart work correctly
