# Timeline Slider Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a timeline slider to the metrics dashboard that allows users to select any historical month and view/capture data for that period.

**Architecture:** The slider lives in the Scores section of ProjectDetail. When a period is selected, it updates query parameters for scores and metrics hooks. If the selected month has no data, an overlay offers to capture it. All data flows through existing React Query patterns.

**Tech Stack:** React, TypeScript, Tailwind CSS, React Query, FastAPI, SQLAlchemy

---

## Task 1: Backend - Add year/month query params to scores endpoint

**Files:**
- Modify: `backend/app/api/scores.py:50-86`
- Test: `backend/tests/test_integration.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_integration.py`:

```python
@pytest.mark.asyncio
class TestScoresAPIWithPeriod:
    """Test scores API with period parameters."""

    async def test_get_scores_with_year_month(
        self, client: AsyncClient, test_project_with_metrics: tuple
    ):
        """Should return scores for specific year/month."""
        project, metrics = test_project_with_metrics
        year = metrics.period_year
        month = metrics.period_month

        response = await client.get(
            f"/api/scores/project/{project.id}",
            params={"year": year, "month": month},
        )
        assert response.status_code == 200
        data = response.json()
        assert "indicators" in data
        assert "scores" in data

    async def test_get_scores_with_nonexistent_period(
        self, client: AsyncClient, test_project: ProjectDB
    ):
        """Should return 404 for period with no metrics."""
        response = await client.get(
            f"/api/scores/project/{test_project.id}",
            params={"year": 2020, "month": 1},
        )
        assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_integration.py::TestScoresAPIWithPeriod -v
```

Expected: FAIL with 422 (unrecognized query params) or wrong behavior

**Step 3: Implement the backend change**

Modify `backend/app/api/scores.py`:

```python
@router.get("/project/{project_id}", response_model=ScoreResponse)
@limiter.limit("100/minute")
async def get_project_scores(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    year: int | None = None,
    month: int | None = None,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
) -> ScoreResponse:
    """Calculate scores from a project's metrics.

    Args:
        year: Optional year to get scores for specific period
        month: Optional month (1-12) to get scores for specific period
        snapshot_type: Filter by snapshot type (default: cumulative)

    If year and month are provided, returns scores for that specific period.
    Otherwise, returns scores from the latest metrics.
    """
    await get_project_or_404(db, project_id)

    if year is not None and month is not None:
        # Get metrics for specific period
        metrics_db = await MetricsService.get_metrics(
            db, project_id, year, month, snapshot_type
        )
        if not metrics_db:
            raise MetricsNotFoundError(str(project_id))
        metrics = MetricsCreate.from_db(metrics_db)
        score_service = ScoreComputationService(config)
        indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)
        return ScoreResponse(indicators=indicators, scores=scores)

    # Default: get latest metrics
    metrics_list = await MetricsService.get_latest_metrics_for_scoring(
        db, project_id, snapshot_type
    )
    if not metrics_list:
        raise MetricsNotFoundError(str(project_id))

    latest_period_end = metrics_list[0].period_end
    same_period = [m for m in metrics_list if m.period_end == latest_period_end]

    metrics_db = _consolidate_metrics(same_period)
    metrics = MetricsCreate.from_db(metrics_db)

    score_service = ScoreComputationService(config)
    indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)

    return ScoreResponse(indicators=indicators, scores=scores)
```

**Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_integration.py::TestScoresAPIWithPeriod -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/scores.py backend/tests/test_integration.py
git commit -m "feat(api): add year/month query params to scores endpoint"
```

---

## Task 2: Frontend - Update API client and query keys

**Files:**
- Modify: `frontend/src/services/api.ts:84-99`
- Modify: `frontend/src/hooks/queryKeys.ts`

**Step 1: Update query keys**

Modify `frontend/src/hooks/queryKeys.ts`:

```typescript
export const queryKeys = {
  projects: {
    all: ['projects'] as const,
    detail: (id: string) => ['projects', id] as const,
  },
  metrics: {
    byProject: (projectId: string) => ['metrics', projectId] as const,
    byPeriod: (projectId: string, year: number, month: number) =>
      ['metrics', projectId, year, month] as const,
  },
  scores: {
    all: ['scores'] as const,
    byProject: (projectId: string) => ['scores', projectId] as const,
    byPeriod: (projectId: string, year: number, month: number) =>
      ['scores', projectId, year, month] as const,
    history: (projectId: string, limit: number) =>
      ['scores', projectId, 'history', limit] as const,
  },
  config: {
    all: ['config'] as const,
    parameters: ['config', 'parameters'] as const,
    validation: ['config', 'validation'] as const,
  },
  snapshots: {
    byProject: (projectId: string) => ['snapshots', projectId] as const,
    history: (projectId: string, limit: number) =>
      ['snapshots', projectId, 'history', limit] as const,
    detail: (projectId: string, year: number, month: number) =>
      ['snapshots', projectId, year, month] as const,
  },
  jobs: {
    all: ['jobs'] as const,
    byProject: (projectId: string) => ['jobs', 'project', projectId] as const,
    detail: (jobId: string) => ['jobs', 'detail', jobId] as const,
  },
} as const;
```

**Step 2: Update API client**

Modify `frontend/src/services/api.ts`:

```typescript
export const scoresApi = {
  getProjectScores: async (
    projectId: string,
    year?: number,
    month?: number,
  ): Promise<ScoreResponse> => {
    const params: Record<string, number> = {};
    if (year !== undefined) params.year = year;
    if (month !== undefined) params.month = month;

    const response = await api.get<ScoreResponse>(
      `/scores/project/${projectId}`,
      { params },
    );
    return response.data;
  },

  getScoreHistory: async (
    projectId: string,
    limit = 10,
  ): Promise<ScoreResponse[]> => {
    const response = await api.get<ScoreResponse[]>(
      `/scores/project/${projectId}/history`,
      { params: { limit } },
    );
    return response.data;
  },

  calculate: async (
    metrics: MetricsCreate,
    sev1Incident = false,
  ): Promise<ScoreResponse> => {
    const response = await api.post<ScoreResponse>('/scores/calculate', {
      metrics,
      sev1_incident: sev1Incident,
    });
    return response.data;
  },
};
```

**Step 3: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/hooks/queryKeys.ts
git commit -m "feat(api): add period params to scores API client"
```

---

## Task 3: Frontend - Update useProjectScores hook

**Files:**
- Modify: `frontend/src/hooks/useScores.ts`

**Step 1: Update the hook**

Modify `frontend/src/hooks/useScores.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { scoresApi, configApi } from '../services/api';
import { queryKeys } from './queryKeys';

export function useProjectScores(
  projectId: string,
  year?: number,
  month?: number,
) {
  const hasPeriod = year !== undefined && month !== undefined;

  return useQuery({
    queryKey: hasPeriod
      ? queryKeys.scores.byPeriod(projectId, year, month)
      : queryKeys.scores.byProject(projectId),
    queryFn: () => scoresApi.getProjectScores(projectId, year, month),
    enabled: !!projectId,
  });
}

export function useScoreHistory(projectId: string, limit = 10) {
  return useQuery({
    queryKey: queryKeys.scores.history(projectId, limit),
    queryFn: () => scoresApi.getScoreHistory(projectId, limit),
    enabled: !!projectId,
  });
}

export function useScoringConfig() {
  return useQuery({
    queryKey: queryKeys.config.all,
    queryFn: configApi.get,
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useScores.ts
git commit -m "feat(hooks): add period params to useProjectScores"
```

---

## Task 4: Frontend - Update useProjectMetrics hook

**Files:**
- Modify: `frontend/src/hooks/useMetrics.ts`

**Step 1: Update the hook**

Modify `frontend/src/hooks/useMetrics.ts`, replace `useProjectMetrics` function:

```typescript
export function useProjectMetrics(
  projectId: string,
  year?: number,
  month?: number,
) {
  const hasPeriod = year !== undefined && month !== undefined;

  return useQuery({
    queryKey: hasPeriod
      ? queryKeys.metrics.byPeriod(projectId, year, month)
      : queryKeys.metrics.byProject(projectId),
    queryFn: async (): Promise<Metrics | null> => {
      try {
        if (hasPeriod) {
          // Get metrics for specific period
          const response = await metricsHistoryApi.getByPeriod(
            projectId,
            year,
            month,
            'cumulative',
          );
          return response;
        }

        // Default: get latest metrics
        const response = await api.get<Metrics[]>(`/metrics/project/${projectId}`);
        if (response.data && response.data.length > 0) {
          const sorted = response.data.sort((a, b) => {
            return new Date(b.period_end).getTime() - new Date(a.period_end).getTime();
          });
          return sorted[0];
        }
        return null;
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}
```

Also add the import at the top:

```typescript
import api, { metricsHistoryApi } from '../services/api';
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useMetrics.ts
git commit -m "feat(hooks): add period params to useProjectMetrics"
```

---

## Task 5: Frontend - Create TimelineSlider component

**Files:**
- Create: `frontend/src/components/ProjectDetail/TimelineSlider.tsx`

**Step 1: Create the component**

Create `frontend/src/components/ProjectDetail/TimelineSlider.tsx`:

```typescript
import { useMemo, useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { MetricsWithScores } from '../../types';

interface Period {
  year: number;
  month: number;
}

interface TimelineSliderProps {
  projectStartDate: string;
  snapshots: MetricsWithScores[] | undefined;
  selectedPeriod: Period | null;
  onPeriodChange: (period: Period | null) => void;
  isCapturing?: boolean;
}

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function formatPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

function generateMonthRange(startDate: string): Period[] {
  const start = new Date(startDate);
  const now = new Date();
  const periods: Period[] = [];

  let year = start.getFullYear();
  let month = start.getMonth() + 1;

  while (
    year < now.getFullYear() ||
    (year === now.getFullYear() && month <= now.getMonth() + 1)
  ) {
    periods.push({ year, month });
    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return periods;
}

export default function TimelineSlider({
  projectStartDate,
  snapshots,
  selectedPeriod,
  onPeriodChange,
  isCapturing = false,
}: TimelineSliderProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);

  const periods = useMemo(
    () => generateMonthRange(projectStartDate),
    [projectStartDate],
  );

  const snapshotSet = useMemo(() => {
    const set = new Set<string>();
    snapshots?.forEach((s) => {
      set.add(`${s.period_year}-${s.period_month}`);
    });
    return set;
  }, [snapshots]);

  const hasData = useCallback(
    (year: number, month: number) => snapshotSet.has(`${year}-${month}`),
    [snapshotSet],
  );

  const isSelected = useCallback(
    (year: number, month: number) =>
      selectedPeriod?.year === year && selectedPeriod?.month === month,
    [selectedPeriod],
  );

  const latestWithData = useMemo(() => {
    for (let i = periods.length - 1; i >= 0; i--) {
      const p = periods[i];
      if (hasData(p.year, p.month)) {
        return p;
      }
    }
    return periods[periods.length - 1];
  }, [periods, hasData]);

  const effectivePeriod = selectedPeriod ?? latestWithData;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const currentIndex = periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      );

      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex - 1]);
      } else if (e.key === 'ArrowRight' && currentIndex < periods.length - 1) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex + 1]);
      }
    },
    [periods, effectivePeriod, onPeriodChange],
  );

  // Scroll selected period into view
  useEffect(() => {
    if (containerRef.current && effectivePeriod) {
      const index = periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      );
      const marker = containerRef.current.children[index] as HTMLElement;
      if (marker) {
        marker.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }
    }
  }, [effectivePeriod, periods]);

  // Show label every N months based on total count
  const labelInterval = periods.length > 24 ? 6 : periods.length > 12 ? 3 : 1;

  return (
    <div
      className="w-full py-4"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="slider"
      aria-label="Timeline period selector"
      aria-valuemin={0}
      aria-valuemax={periods.length - 1}
      aria-valuenow={periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      )}
    >
      <div className="relative">
        {/* Base line */}
        <div className="absolute top-3 left-0 right-0 h-0.5 bg-muted" />

        {/* Markers container */}
        <div
          ref={containerRef}
          className="relative flex justify-between overflow-x-auto pb-6 scrollbar-thin"
          style={{ minWidth: `${periods.length * 40}px` }}
        >
          <TooltipProvider>
            {periods.map((period, index) => {
              const hasPeriodData = hasData(period.year, period.month);
              const isPeriodSelected = isSelected(period.year, period.month);
              const isEffective =
                !selectedPeriod &&
                period.year === latestWithData.year &&
                period.month === latestWithData.month;
              const showLabel = index % labelInterval === 0;

              return (
                <Tooltip key={`${period.year}-${period.month}`}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => onPeriodChange(period)}
                      className={cn(
                        'relative flex flex-col items-center transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        'min-w-[40px]',
                      )}
                    >
                      {/* Marker */}
                      <div
                        className={cn(
                          'w-3 h-3 rounded-full border-2 transition-all',
                          hasPeriodData
                            ? 'bg-primary border-primary'
                            : 'bg-background border-muted-foreground/50',
                          (isPeriodSelected || isEffective) && [
                            'w-5 h-5 ring-4 ring-primary/20',
                            hasPeriodData ? 'bg-primary' : 'border-primary',
                          ],
                          isCapturing &&
                            isPeriodSelected &&
                            'animate-pulse',
                        )}
                      />

                      {/* Label */}
                      {showLabel && (
                        <span
                          className={cn(
                            'absolute top-6 text-xs text-muted-foreground whitespace-nowrap',
                            (isPeriodSelected || isEffective) &&
                              'text-foreground font-medium',
                          )}
                        >
                          {formatPeriod(period.year, period.month)}
                        </span>
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      {formatPeriod(period.year, period.month)}
                      {hasPeriodData ? '' : ' (no data)'}
                    </p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>
      </div>

      {/* Reset button */}
      {selectedPeriod && (
        <button
          type="button"
          onClick={() => onPeriodChange(null)}
          className="mt-2 text-xs text-muted-foreground hover:text-foreground underline"
        >
          Reset to latest
        </button>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ProjectDetail/TimelineSlider.tsx
git commit -m "feat(ui): create TimelineSlider component"
```

---

## Task 6: Frontend - Create EmptyPeriodOverlay component

**Files:**
- Create: `frontend/src/components/ProjectDetail/EmptyPeriodOverlay.tsx`

**Step 1: Create the component**

Create `frontend/src/components/ProjectDetail/EmptyPeriodOverlay.tsx`:

```typescript
import { Button } from '@/components/ui/button';
import { Loader2, Calendar } from 'lucide-react';

interface Period {
  year: number;
  month: number;
}

interface EmptyPeriodOverlayProps {
  period: Period;
  onCapture: () => void;
  isCapturing: boolean;
  error?: Error | null;
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

export default function EmptyPeriodOverlay({
  period,
  onCapture,
  isCapturing,
  error,
}: EmptyPeriodOverlayProps): JSX.Element {
  const periodLabel = `${MONTH_NAMES[period.month - 1]} ${period.year}`;

  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-lg">
      <div className="text-center space-y-4 p-6">
        <Calendar className="w-12 h-12 mx-auto text-muted-foreground" />
        <div>
          <h3 className="text-lg font-semibold">No data for {periodLabel}</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Capture metrics from Jira and GitHub for this period
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive">
            {error.message || 'Failed to capture metrics. Please try again.'}
          </p>
        )}

        <Button onClick={onCapture} disabled={isCapturing}>
          {isCapturing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Capturing...
            </>
          ) : (
            'Capture metrics for this period'
          )}
        </Button>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ProjectDetail/EmptyPeriodOverlay.tsx
git commit -m "feat(ui): create EmptyPeriodOverlay component"
```

---

## Task 7: Frontend - Export new components

**Files:**
- Modify: `frontend/src/components/ProjectDetail/index.ts`

**Step 1: Add exports**

Add to `frontend/src/components/ProjectDetail/index.ts`:

```typescript
export { default as TimelineSlider } from './TimelineSlider';
export { default as EmptyPeriodOverlay } from './EmptyPeriodOverlay';
```

**Step 2: Commit**

```bash
git add frontend/src/components/ProjectDetail/index.ts
git commit -m "feat(ui): export TimelineSlider and EmptyPeriodOverlay"
```

---

## Task 8: Frontend - Integrate TimelineSlider into ProjectDetail

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

**Step 1: Update ProjectDetail**

Modify `frontend/src/pages/ProjectDetail.tsx`:

1. Add imports at the top:

```typescript
import {
  ProjectHeader,
  ProjectDialogs,
  CollectorNotifications,
  EVMSection,
  QualityMetricsGrid,
  DORASection,
  SnapshotManager,
  TimelineSlider,
  EmptyPeriodOverlay,
} from '../components/ProjectDetail';
import { useCapturePeriod } from '../hooks/usePeriodCapture';
```

2. Add state for selected period after `visibleDimensions` state:

```typescript
const [selectedPeriod, setSelectedPeriod] = useState<{ year: number; month: number } | null>(null);
```

3. Update hooks to use selected period:

```typescript
const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(
  id!,
  selectedPeriod?.year,
  selectedPeriod?.month,
);
const { data: metrics } = useProjectMetrics(
  id!,
  selectedPeriod?.year,
  selectedPeriod?.month,
);
```

4. Add capture period hook:

```typescript
const {
  mutateAsync: capturePeriod,
  isPending: isPeriodCapturing,
  error: periodCaptureError,
} = useCapturePeriod(id!);
```

5. Add handler for period capture:

```typescript
const handleCapturePeriod = async (): Promise<void> => {
  if (!selectedPeriod) return;
  await capturePeriod({
    year: selectedPeriod.year,
    month: selectedPeriod.month,
    force: false,
  });
};
```

6. Add helper to check if period has data:

```typescript
const periodHasData = useMemo(() => {
  if (!selectedPeriod || !snapshots) return true;
  return snapshots.some(
    (s) => s.period_year === selectedPeriod.year && s.period_month === selectedPeriod.month,
  );
}, [selectedPeriod, snapshots]);
```

7. Update the scores section JSX (after the Separator inside `{scores && (...)}`):

Replace the scores section with:

```tsx
{scores && (
  <>
    <Separator className="my-6" />
    <div>
      <h2 className="text-2xl font-semibold mb-4">Scores</h2>

      {project.start_date && (
        <TimelineSlider
          projectStartDate={project.start_date}
          snapshots={snapshots}
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
          isCapturing={isPeriodCapturing}
        />
      )}

      <div className="relative">
        {selectedPeriod && !periodHasData && (
          <EmptyPeriodOverlay
            period={selectedPeriod}
            onCapture={handleCapturePeriod}
            isCapturing={isPeriodCapturing}
            error={periodCaptureError}
          />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ScoreCard
            score={scores.scores}
            snapshots={snapshots}
            visibleDimensions={visibleDimensions}
            onToggleDimension={handleToggleDimension}
            onResetFilters={handleResetFilters}
          />
          <DimensionChart
            scores={scores.scores.dimensions}
            snapshots={snapshots}
            visibleDimensions={visibleDimensions}
            onToggleDimension={handleToggleDimension}
          />
        </div>
      </div>
    </div>

    <EVMSection
      evmData={metrics?.evm_data}
      milestones={metrics?.milestones}
      indicators={scores.indicators}
      onUpdateEVM={handleUpdateEVM}
      onUpdateMilestones={handleUpdateMilestones}
      isUpdatingEVM={updateEVM.isPending}
      isUpdatingMilestones={updateMilestones.isPending}
      getTarget={getTarget}
      getConstant={getConstant}
      snapshots={snapshots}
      visibleDimensions={visibleDimensions}
    />
  </>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "feat(ui): integrate TimelineSlider into ProjectDetail"
```

---

## Task 9: Frontend - Add unit tests for TimelineSlider

**Files:**
- Create: `frontend/src/components/ProjectDetail/TimelineSlider.test.tsx`

**Step 1: Create tests**

Create `frontend/src/components/ProjectDetail/TimelineSlider.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TimelineSlider from './TimelineSlider';

const mockSnapshots = [
  { period_year: 2025, period_month: 10 },
  { period_year: 2025, period_month: 11 },
  { period_year: 2025, period_month: 12 },
] as any[];

describe('TimelineSlider', () => {
  it('renders all months from start date to now', () => {
    const startDate = '2025-10-01';
    render(
      <TimelineSlider
        projectStartDate={startDate}
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Oct 2025')).toBeInTheDocument();
  });

  it('calls onPeriodChange when clicking a month', () => {
    const onPeriodChange = vi.fn();
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={onPeriodChange}
      />,
    );

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);

    expect(onPeriodChange).toHaveBeenCalledWith({ year: 2025, month: 10 });
  });

  it('shows reset button when period is selected', () => {
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={{ year: 2025, month: 10 }}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Reset to latest')).toBeInTheDocument();
  });

  it('hides reset button when no period selected', () => {
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.queryByText('Reset to latest')).not.toBeInTheDocument();
  });

  it('shows pulse animation when capturing', () => {
    const { container } = render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={{ year: 2025, month: 10 }}
        onPeriodChange={vi.fn()}
        isCapturing
      />,
    );

    const animatedElement = container.querySelector('.animate-pulse');
    expect(animatedElement).toBeInTheDocument();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- TimelineSlider
```

Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/ProjectDetail/TimelineSlider.test.tsx
git commit -m "test(ui): add TimelineSlider unit tests"
```

---

## Task 10: Integration testing

**Step 1: Run all backend tests**

```bash
cd backend && pytest -v
```

Expected: All tests pass

**Step 2: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: All tests pass

**Step 3: Manual testing**

1. Start backend: `cd backend && python run_server.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to a project with historical data
4. Verify:
   - Timeline slider appears in Scores section
   - Months with data show filled markers
   - Months without data show empty markers
   - Clicking a month updates all displayed data
   - Clicking empty month shows capture overlay
   - Keyboard navigation works (arrow keys)
   - "Reset to latest" returns to default view

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete timeline slider for period selection

- Backend: scores endpoint accepts year/month params
- Frontend: TimelineSlider component with keyboard navigation
- Frontend: EmptyPeriodOverlay for months without data
- Integration with existing capture period flow
"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Backend: Add year/month params to scores endpoint | `backend/app/api/scores.py` |
| 2 | Frontend: Update API client and query keys | `frontend/src/services/api.ts`, `queryKeys.ts` |
| 3 | Frontend: Update useProjectScores hook | `frontend/src/hooks/useScores.ts` |
| 4 | Frontend: Update useProjectMetrics hook | `frontend/src/hooks/useMetrics.ts` |
| 5 | Frontend: Create TimelineSlider component | `TimelineSlider.tsx` |
| 6 | Frontend: Create EmptyPeriodOverlay component | `EmptyPeriodOverlay.tsx` |
| 7 | Frontend: Export new components | `index.ts` |
| 8 | Frontend: Integrate into ProjectDetail | `ProjectDetail.tsx` |
| 9 | Frontend: Add unit tests | `TimelineSlider.test.tsx` |
| 10 | Integration testing | Manual verification |
