# Plan: Global Metrics Dashboard

**Branch:** `feature/global-metrics`
**Status:** READY FOR IMPLEMENTATION

## Overview

Add a global metrics dashboard that displays averaged indicators and scores across all projects. Monthly records stored in DB enable trend tracking, ISO reporting, and recalculation with different weights.

## Core Concept

- Calculate **monthly averages** from all projects' **cumulative** metrics
- **Batch calculation only** - no on-the-fly (allows recalculation with new weights)
- Store in `global_metrics` table (same pattern as `metrics` table)
- Per-indicator project count (only projects with data count toward average)
- UI similar to ProjectDetail but simplified (no collectors, read-only)

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Stored only (no on-the-fly) | Allows recalculation with new weights; better performance |
| Per-indicator counts | Each metric may have different project coverage |
| Timeline from 2023 | Practical historical limit |
| Sync batch (no ARQ) | No external APIs - just DB queries + calculations |

---

## Phase 1: Backend - Database & Models

### 1.1 Create GlobalMetrics Model

**File:** `backend/app/models/global_metrics.py`

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
    project_count = Column(Integer, nullable=False)  # Total projects with any metrics
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Averaged Indicators (0-1 scale) + their project counts
    spi = Column(Float, nullable=True)
    spi_count = Column(Integer, nullable=True)
    cpi = Column(Float, nullable=True)
    cpi_count = Column(Integer, nullable=True)
    on_time_milestones = Column(Float, nullable=True)
    on_time_milestones_count = Column(Integer, nullable=True)
    defect_density = Column(Float, nullable=True)
    defect_density_count = Column(Integer, nullable=True)
    escaped_rate = Column(Float, nullable=True)
    escaped_rate_count = Column(Integer, nullable=True)
    mttr_hours = Column(Float, nullable=True)
    mttr_hours_count = Column(Integer, nullable=True)
    governance_compliance = Column(Float, nullable=True)
    governance_compliance_count = Column(Integer, nullable=True)
    lead_time_days = Column(Float, nullable=True)
    lead_time_days_count = Column(Integer, nullable=True)
    deployment_frequency = Column(Float, nullable=True)
    deployment_frequency_count = Column(Integer, nullable=True)
    change_failure_rate = Column(Float, nullable=True)
    change_failure_rate_count = Column(Integer, nullable=True)
    commitment_reliability = Column(Float, nullable=True)
    commitment_reliability_count = Column(Integer, nullable=True)
    pr_review_ratio = Column(Float, nullable=True)
    pr_review_ratio_count = Column(Integer, nullable=True)
    test_maturity = Column(Float, nullable=True)
    test_maturity_count = Column(Integer, nullable=True)
    arch_checklist = Column(Float, nullable=True)
    arch_checklist_count = Column(Integer, nullable=True)
    high_vulns = Column(Float, nullable=True)
    high_vulns_count = Column(Integer, nullable=True)
    okr_impact = Column(Float, nullable=True)
    okr_impact_count = Column(Integer, nullable=True)
    pm_satisfaction = Column(Float, nullable=True)
    pm_satisfaction_count = Column(Integer, nullable=True)
    client_satisfaction = Column(Float, nullable=True)
    client_satisfaction_count = Column(Integer, nullable=True)
    story_review_ratio = Column(Float, nullable=True)
    story_review_ratio_count = Column(Integer, nullable=True)
    strategic_impact = Column(Float, nullable=True)  # Numeric average
    strategic_impact_count = Column(Integer, nullable=True)

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

class IndicatorValue(BaseModel):
    """Indicator with its value and project count."""
    value: float | None = None
    count: int = 0

class GlobalIndicators(BaseModel):
    spi: IndicatorValue = IndicatorValue()
    cpi: IndicatorValue = IndicatorValue()
    on_time_milestones: IndicatorValue = IndicatorValue()
    defect_density: IndicatorValue = IndicatorValue()
    escaped_rate: IndicatorValue = IndicatorValue()
    mttr_hours: IndicatorValue = IndicatorValue()
    governance_compliance: IndicatorValue = IndicatorValue()
    lead_time_days: IndicatorValue = IndicatorValue()
    deployment_frequency: IndicatorValue = IndicatorValue()
    change_failure_rate: IndicatorValue = IndicatorValue()
    commitment_reliability: IndicatorValue = IndicatorValue()
    pr_review_ratio: IndicatorValue = IndicatorValue()
    test_maturity: IndicatorValue = IndicatorValue()
    arch_checklist: IndicatorValue = IndicatorValue()
    high_vulns: IndicatorValue = IndicatorValue()
    okr_impact: IndicatorValue = IndicatorValue()
    pm_satisfaction: IndicatorValue = IndicatorValue()
    client_satisfaction: IndicatorValue = IndicatorValue()
    story_review_ratio: IndicatorValue = IndicatorValue()
    strategic_impact: IndicatorValue = IndicatorValue()

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

class GlobalMetricsRecord(BaseModel):
    """Response for a stored global metrics record."""
    id: str
    period_year: int
    period_month: int
    project_count: int
    indicators: GlobalIndicators
    scores: GlobalScores
    created_at: datetime
    updated_at: datetime

class GlobalMetricsHistoryResponse(BaseModel):
    """Response for historical global metrics query."""
    records: list[GlobalMetricsRecord]

class CalculateBatchRequest(BaseModel):
    """Request to calculate global metrics for a date range."""
    from_year: int
    from_month: int
    to_year: int
    to_month: int

class CalculateBatchResponse(BaseModel):
    """Response from batch calculation."""
    months_processed: int
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
from datetime import datetime
from app.models.metrics import MetricsDB
from app.models.global_metrics import (
    GlobalMetricsDB,
    GlobalIndicators,
    GlobalScores,
    GlobalMetricsRecord,
    IndicatorValue,
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

    async def calculate_and_store(
        self,
        db: AsyncSession,
        year: int,
        month: int,
    ) -> GlobalMetricsDB:
        """Calculate global averages for a specific month and store in DB."""

        # Fetch all cumulative metrics for this period
        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.period_year == year)
            .where(MetricsDB.period_month == month)
            .where(MetricsDB.snapshot_type == "cumulative")
        )
        metrics_list = result.scalars().all()

        # Calculate averages with counts
        indicators = self._average_indicators(metrics_list)
        scores = self._calculate_scores(indicators)

        # Upsert
        return await self._upsert(db, year, month, len(metrics_list), indicators, scores)

    def _average_indicators(self, metrics_list: list[MetricsDB]) -> GlobalIndicators:
        """Calculate average for each indicator, tracking count of non-null values."""
        indicator_data = {}

        for field in INDICATOR_FIELDS:
            values = [
                getattr(m, field)
                for m in metrics_list
                if getattr(m, field) is not None
            ]
            indicator_data[field] = IndicatorValue(
                value=sum(values) / len(values) if values else None,
                count=len(values)
            )

        # Handle strategic_impact separately (category -> numeric -> average)
        impact_values = [
            STRATEGIC_IMPACT_VALUES.get(m.strategic_impact)
            for m in metrics_list
            if m.strategic_impact in STRATEGIC_IMPACT_VALUES
        ]
        indicator_data['strategic_impact'] = IndicatorValue(
            value=sum(impact_values) / len(impact_values) if impact_values else None,
            count=len(impact_values)
        )

        return GlobalIndicators(**indicator_data)

    def _calculate_scores(self, indicators: GlobalIndicators) -> GlobalScores:
        """Calculate dimension scores from averaged indicators."""
        # Reuse existing dimension calculators with averaged indicator values
        # Each calculator takes normalized indicators and returns 0-100 score
        # TODO: Wire up existing calculators
        return GlobalScores()

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

        # Flatten indicators to DB columns
        indicator_cols = {}
        for field in INDICATOR_FIELDS + ['strategic_impact']:
            ind = getattr(indicators, field)
            indicator_cols[field] = ind.value
            indicator_cols[f"{field}_count"] = ind.count

        if existing:
            for key, value in indicator_cols.items():
                setattr(existing, key, value)
            for key, value in scores.model_dump().items():
                setattr(existing, key, value)
            existing.project_count = project_count
            existing.updated_at = datetime.utcnow()
            record = existing
        else:
            record = GlobalMetricsDB(
                period_year=year,
                period_month=month,
                project_count=project_count,
                **indicator_cols,
                **scores.model_dump(),
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    async def calculate_batch(
        self,
        db: AsyncSession,
        from_year: int,
        from_month: int,
        to_year: int,
        to_month: int,
    ) -> list[GlobalMetricsDB]:
        """Calculate global metrics for a range of months."""
        records = []

        year, month = from_year, from_month
        while (year, month) <= (to_year, to_month):
            record = await self.calculate_and_store(db, year, month)
            records.append(record)

            # Next month
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
                GlobalMetricsDB.period_month.desc()
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def get_available_months(
        self,
        db: AsyncSession,
    ) -> list[tuple[int, int]]:
        """Get list of months that have stored global metrics."""
        result = await db.execute(
            select(GlobalMetricsDB.period_year, GlobalMetricsDB.period_month)
            .order_by(
                GlobalMetricsDB.period_year.desc(),
                GlobalMetricsDB.period_month.desc()
            )
        )
        return [(r.period_year, r.period_month) for r in result.all()]
```

---

## Phase 3: Backend - API Endpoints

### 3.1 Create Global API Router

**File:** `backend/app/api/global_metrics.py`

```python
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.global_metrics_service import GlobalMetricsService
from app.services.scoring_config import ScoringConfig
from app.models.global_metrics import (
    GlobalMetricsRecord,
    GlobalMetricsHistoryResponse,
    CalculateBatchRequest,
    CalculateBatchResponse,
)

router = APIRouter(prefix="/api/global", tags=["global"])

def get_global_service() -> GlobalMetricsService:
    config = ScoringConfig()
    return GlobalMetricsService(config)

def _db_to_response(record) -> GlobalMetricsRecord:
    """Convert DB model to response schema."""
    # TODO: Implement conversion
    pass

@router.get("/{year}/{month}", response_model=GlobalMetricsRecord | None)
async def get_global_metrics(
    year: int,
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Get stored global metrics for a specific month."""
    record = await service.get_record(db, year, month)
    if not record:
        return None
    return _db_to_response(record)

@router.get("/history", response_model=GlobalMetricsHistoryResponse)
async def get_global_metrics_history(
    limit: int = Query(12, ge=1, le=48),
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Get historical global metrics for trend display."""
    records = await service.get_history(db, limit)
    return GlobalMetricsHistoryResponse(
        records=[_db_to_response(r) for r in records]
    )

@router.get("/available-months")
async def get_available_months(
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
) -> list[dict]:
    """Get list of months that have stored global metrics."""
    months = await service.get_available_months(db)
    return [{"year": y, "month": m} for y, m in months]

@router.post("/calculate", response_model=CalculateBatchResponse)
async def calculate_global_metrics(
    request: CalculateBatchRequest,
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Calculate and store global metrics for a date range (batch)."""
    if (request.from_year, request.from_month) > (request.to_year, request.to_month):
        raise HTTPException(400, "from_date must be before to_date")

    if request.from_year < 2023:
        raise HTTPException(400, "from_year must be 2023 or later")

    records = await service.calculate_batch(
        db,
        request.from_year,
        request.from_month,
        request.to_year,
        request.to_month,
    )
    return CalculateBatchResponse(
        months_processed=len(records),
        records=[_db_to_response(r) for r in records],
    )

@router.post("/recalculate", response_model=CalculateBatchResponse)
async def recalculate_global_metrics(
    request: CalculateBatchRequest,
    db: AsyncSession = Depends(get_db),
    service: GlobalMetricsService = Depends(get_global_service),
):
    """Recalculate global metrics with current weights for a date range."""
    # Same as calculate - upsert handles overwriting
    return await calculate_global_metrics(request, db, service)
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
export interface IndicatorValue {
  value: number | null;
  count: number;
}

export interface GlobalIndicators {
  spi: IndicatorValue;
  cpi: IndicatorValue;
  on_time_milestones: IndicatorValue;
  defect_density: IndicatorValue;
  escaped_rate: IndicatorValue;
  mttr_hours: IndicatorValue;
  governance_compliance: IndicatorValue;
  lead_time_days: IndicatorValue;
  deployment_frequency: IndicatorValue;
  change_failure_rate: IndicatorValue;
  commitment_reliability: IndicatorValue;
  pr_review_ratio: IndicatorValue;
  test_maturity: IndicatorValue;
  arch_checklist: IndicatorValue;
  high_vulns: IndicatorValue;
  okr_impact: IndicatorValue;
  pm_satisfaction: IndicatorValue;
  client_satisfaction: IndicatorValue;
  story_review_ratio: IndicatorValue;
  strategic_impact: IndicatorValue;
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

export interface GlobalMetricsRecord {
  id: string;
  period_year: number;
  period_month: number;
  project_count: number;
  indicators: GlobalIndicators;
  scores: GlobalScores;
  created_at: string;
  updated_at: string;
}

export interface CalculateBatchRequest {
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
}

export interface CalculateBatchResponse {
  months_processed: number;
  records: GlobalMetricsRecord[];
}
```

### 4.2 Add Query Keys

**File:** `frontend/src/hooks/queryKeys.ts`

```typescript
// Add to existing queryKeys
global: {
  all: ['global'] as const,
  record: (year: number, month: number) =>
    ['global', 'record', year, month] as const,
  history: (limit?: number) =>
    ['global', 'history', limit] as const,
  availableMonths: ['global', 'available-months'] as const,
},
```

### 4.3 Create Hooks

**File:** `frontend/src/hooks/useGlobalMetrics.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { queryKeys } from './queryKeys';
import type {
  GlobalMetricsRecord,
  CalculateBatchRequest,
  CalculateBatchResponse,
} from '../types/global';

export function useGlobalMetrics(year: number, month: number) {
  return useQuery({
    queryKey: queryKeys.global.record(year, month),
    queryFn: async (): Promise<GlobalMetricsRecord | null> => {
      const response = await api.get(`/api/global/${year}/${month}`);
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

export function useAvailableGlobalMonths() {
  return useQuery({
    queryKey: queryKeys.global.availableMonths,
    queryFn: async (): Promise<{ year: number; month: number }[]> => {
      const response = await api.get('/api/global/available-months');
      return response.data;
    },
  });
}

export function useCalculateGlobalMetrics() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CalculateBatchRequest): Promise<CalculateBatchResponse> => {
      const response = await api.post('/api/global/calculate', request);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.global.all });
    },
  });
}

export function useRecalculateGlobalMetrics() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CalculateBatchRequest): Promise<CalculateBatchResponse> => {
      const response = await api.post('/api/global/recalculate', request);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.global.all });
    },
  });
}
```

---

## Phase 5: Frontend - Global Dashboard Page

### 5.1 Create Page Component

**File:** `frontend/src/pages/GlobalDashboard.tsx`

```typescript
import { useState, useMemo } from 'react';
import {
  useGlobalMetrics,
  useGlobalMetricsHistory,
  useAvailableGlobalMonths,
  useCalculateGlobalMetrics,
} from '../hooks/useGlobalMetrics';
import { useConfigParameters } from '../hooks/useConfig';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import TimelineSlider from '../components/ProjectDetail/TimelineSlider';
import { ALL_DIMENSIONS, type Dimension } from '../types';
import { Calculator, RefreshCw } from 'lucide-react';

export default function GlobalDashboard(): JSX.Element {
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [visibleDimensions, setVisibleDimensions] = useState<Set<Dimension>>(
    new Set(ALL_DIMENSIONS)
  );

  const { data: globalMetrics, isLoading } = useGlobalMetrics(selectedYear, selectedMonth);
  const { data: history } = useGlobalMetricsHistory(12);
  const { data: availableMonths } = useAvailableGlobalMonths();
  const { data: config } = useConfigParameters();
  const calculateMutation = useCalculateGlobalMetrics();

  // Build timeline months (last 12 months by default, expandable to 2023)
  const timelineMonths = useMemo(() => {
    const months: { year: number; month: number }[] = [];
    const start = new Date(2023, 0, 1);
    const end = new Date();

    let current = new Date(start);
    while (current <= end) {
      months.push({
        year: current.getFullYear(),
        month: current.getMonth() + 1,
      });
      current.setMonth(current.getMonth() + 1);
    }
    return months;
  }, []);

  // Check which months have data
  const monthsWithData = useMemo(() => {
    if (!availableMonths) return new Set<string>();
    return new Set(availableMonths.map(m => `${m.year}-${m.month}`));
  }, [availableMonths]);

  const handlePeriodChange = (year: number, month: number) => {
    setSelectedYear(year);
    setSelectedMonth(month);
  };

  const handleCalculateAll = () => {
    calculateMutation.mutate({
      from_year: 2023,
      from_month: 1,
      to_year: now.getFullYear(),
      to_month: now.getMonth() + 1,
    });
  };

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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const hasData = globalMetrics !== null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Global Metrics</h1>
          <p className="text-muted-foreground mt-1">
            {hasData
              ? `Averaged across ${globalMetrics.project_count} projects`
              : 'No data for selected period'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleCalculateAll}
            disabled={calculateMutation.isPending}
          >
            <Calculator className="w-4 h-4 mr-2" />
            {calculateMutation.isPending ? 'Calculating...' : 'Calculate All'}
          </Button>
          <Button
            variant="outline"
            onClick={handleCalculateAll}
            disabled={calculateMutation.isPending}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Recalculate
          </Button>
        </div>
      </div>

      {/* Timeline Selector */}
      <Card>
        <CardContent className="pt-6">
          <TimelineSlider
            months={timelineMonths}
            selectedYear={selectedYear}
            selectedMonth={selectedMonth}
            onPeriodChange={handlePeriodChange}
            monthsWithData={monthsWithData}
          />
        </CardContent>
      </Card>

      {!hasData ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-muted-foreground mb-4">
              No global metrics calculated for {selectedMonth}/{selectedYear}
            </p>
            <Button onClick={() => calculateMutation.mutate({
              from_year: selectedYear,
              from_month: selectedMonth,
              to_year: selectedYear,
              to_month: selectedMonth,
            })}>
              Calculate This Month
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ScoreCard
              score={{
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
              }}
              snapshots={history}
              visibleDimensions={visibleDimensions}
              onToggleDimension={handleToggleDimension}
              onResetFilters={handleResetFilters}
            />
            <DimensionChart
              scores={{
                p_time: globalMetrics.scores.p_time ?? 0,
                p_cost: globalMetrics.scores.p_cost ?? 0,
                p_quality: globalMetrics.scores.p_quality ?? 0,
                p_value: globalMetrics.scores.p_value ?? 0,
                p_satisfaction: globalMetrics.scores.p_satisfaction ?? 0,
                p_flow: globalMetrics.scores.p_flow ?? 0,
                p_engineering: globalMetrics.scores.p_engineering ?? 0,
                p_risk: globalMetrics.scores.p_risk ?? 0,
              }}
              snapshots={history}
              visibleDimensions={visibleDimensions}
              onToggleDimension={handleToggleDimension}
            />
          </div>

          <Separator className="my-6" />

          {/* Sub-indicators with project counts */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Example indicator card showing count */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">SPI</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {globalMetrics.indicators.spi.value?.toFixed(2) ?? '-'}
                </div>
                <p className="text-xs text-muted-foreground">
                  {globalMetrics.indicators.spi.count} projects
                </p>
              </CardContent>
            </Card>
            {/* TODO: Add cards for all indicators */}
          </div>
        </>
      )}
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
        """Test that null values don't affect average - divides by count with data."""
        pass

    def test_average_indicators_empty_list(self):
        """Test with no metrics returns empty response."""
        pass

    def test_indicator_counts_tracked(self):
        """Test that each indicator tracks its own project count."""
        pass

    def test_strategic_impact_conversion(self):
        """Test category to numeric conversion for averaging."""
        pass

    def test_calculate_scores_from_indicators(self):
        """Test score calculation using current weights."""
        pass

    def test_upsert_creates_new_record(self):
        """Test insert when no record exists."""
        pass

    def test_upsert_updates_existing_record(self):
        """Test update (recalculate) when record exists for period."""
        pass

    def test_batch_calculate_range(self):
        """Test calculating multiple months in sequence."""
        pass

class TestGlobalAPI:
    async def test_get_stored_metrics(self, client):
        """Test GET /api/global/{year}/{month}."""
        pass

    async def test_get_returns_none_when_no_data(self, client):
        """Test returns null when month not calculated."""
        pass

    async def test_calculate_batch(self, client):
        """Test POST /api/global/calculate."""
        pass

    async def test_calculate_validates_date_range(self, client):
        """Test from_date must be before to_date."""
        pass

    async def test_calculate_validates_min_year(self, client):
        """Test from_year must be 2023 or later."""
        pass

    async def test_get_history(self, client):
        """Test GET /api/global/history."""
        pass

    async def test_get_available_months(self, client):
        """Test GET /api/global/available-months."""
        pass

    async def test_recalculate_overwrites(self, client):
        """Test POST /api/global/recalculate overwrites existing."""
        pass
```

### 6.2 Frontend Tests

**File:** `frontend/src/pages/__tests__/GlobalDashboard.test.tsx`

```typescript
describe('GlobalDashboard', () => {
  it('renders loading state', () => {});
  it('renders empty state when no data', () => {});
  it('displays project count when data exists', () => {});
  it('renders score cards with correct values', () => {});
  it('renders dimension chart', () => {});
  it('shows indicator counts', () => {});
  it('timeline shows months with/without data differently', () => {});
  it('calculate button triggers batch calculation', () => {});
  it('period change updates selected month', () => {});
});
```

---

## Implementation Order

1. **Phase 1**: Database model & migration
2. **Phase 2**: Calculation service (core logic with counts)
3. **Phase 3**: API endpoints
4. **Phase 4**: Frontend types & hooks
5. **Phase 5**: Global dashboard page with timeline
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

## Key Design Decisions Summary

| Aspect | Decision |
|--------|----------|
| Calculation | Batch only (no on-the-fly) - enables recalculation with new weights |
| Storage | Same pattern as `metrics` table with `period_year`/`period_month` |
| Counts | Per-indicator project counts stored in DB (`spi_count`, `cpi_count`, etc.) |
| Timeline | Default 12 months, expandable from 2023 |
| UI | Read-only, no collectors, timeline selector + calculate/recalculate buttons |
| API | Sync batch processing (no ARQ needed - just DB queries) |

## Verification

1. Run backend tests: `pytest tests/test_global_metrics.py`
2. Run frontend tests: `npm test`
3. Manual test: Navigate to `/global`, verify empty state
4. Click "Calculate All", verify data populates
5. Change weights in config, click "Recalculate", verify scores update
6. Navigate timeline, verify months with/without data display correctly
