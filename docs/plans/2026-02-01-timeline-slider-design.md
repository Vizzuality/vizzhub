# Timeline Slider for Period Selection

## Overview

Add a timeline slider to the metrics dashboard that allows users to select a specific month from the project's history. Currently, the dashboard shows only the latest metrics; this feature enables viewing historical data for any month since project start.

## Requirements

- **Slider location**: Inside the Scores section, above ScoreCard and DimensionChart
- **Range**: From `project.start_date` to current month
- **Snapshot type**: Always cumulative (project-to-date metrics)
- **Empty months**: Offer to capture data when selecting a month without snapshots
- **Default**: Latest month with data (preserves current behavior)

## Visual Design

### Slider Component

```
[●]────[●]────[○]────[●]────[◉]
Jan    Feb    Mar    Apr    May
2025   2025   2025   2025   2025
```

**Legend:**
- `●` Filled circle: month with captured data
- `○` Empty circle: month without data
- `◉` Large circle with highlight: currently selected month

**Visual elements:**
- Base bar: horizontal light gray line
- Month markers: points on the line, one per month in range
- Filled markers: primary color (have cumulative snapshot)
- Empty markers: border only, no fill (no data)
- Active selector: larger circle with highlight indicating selected month
- Labels: month/year below markers (show every 3-4 months to avoid clutter, or all if space allows)
- Tooltip on hover: shows "Jan 2025" when hovering any marker

**Interactions:**
- Click on marker → selects that period
- Drag selector → fluid navigation between months
- Arrow keys ← → → move to previous/next month

### Empty State

When user selects a month without cumulative snapshot:

- Components (ScoreCard, DimensionChart, etc.) show semi-transparent overlay
- Centered message: "No data for [Month Year]"
- Primary button: "Capture metrics for this period"
- Secondary text: "Will collect data from Jira and GitHub for this month"

**Capture flow:**
1. Click "Capture metrics" → calls `useCapturePeriod` with `{ year, month, force: false }`
2. Shows spinner/loading on button
3. On complete → slider marker changes to filled
4. Dashboard displays newly captured data
5. On error → shows inline error with retry option

**Visual indicator during capture:**
- Selected month marker pulses/animates while capturing
- Toast on completion: "Data for [Month Year] captured"

## Technical Implementation

### New Component

```
frontend/src/components/ProjectDetail/TimelineSlider.tsx
```

**Props:**
```typescript
interface TimelineSliderProps {
  projectStartDate: string;
  snapshots: MetricsWithScores[];
  selectedPeriod: { year: number; month: number } | null;
  onPeriodChange: (period: { year: number; month: number } | null) => void;
  isCapturing?: boolean;
}
```

### State in ProjectDetail.tsx

```typescript
const [selectedPeriod, setSelectedPeriod] = useState<{year: number; month: number} | null>(null);
```

When `selectedPeriod` is `null`, use latest data (current behavior).

### Data Flow

```
TimelineSlider
    ↓ onPeriodChange({ year: 2025, month: 6 })
ProjectDetail (state update)
    ↓ passes year/month to hooks
useProjectScores(id, year, month)
useProjectMetrics(id, year, month)
    ↓ queries with parameters
GET /api/scores/project/{id}?year=2025&month=6
GET /api/metrics/project/{id}?year=2025&month=6
    ↓ returns period-specific data
Components render with selected period data
```

### Hook Changes

**useProjectScores:**
```typescript
// Before
export function useProjectScores(projectId: string)

// After
export function useProjectScores(
  projectId: string,
  year?: number,
  month?: number
)
```

**useProjectMetrics:**
```typescript
// Before
export function useProjectMetrics(projectId: string)

// After
export function useProjectMetrics(
  projectId: string,
  year?: number,
  month?: number
)
```

### Backend Changes

**Scores endpoint** needs to accept optional year/month query parameters:

```python
@router.get("/project/{project_id}")
async def get_project_scores(
    project_id: UUID,
    year: int | None = None,
    month: int | None = None,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
    db: DBSession,
):
    # If year/month provided, get metrics for that period
    # Otherwise, get latest metrics (current behavior)
```

The metrics endpoint already supports `/api/metrics/project/{id}/{year}/{month}`, but we'll add query param support for consistency.

### Affected Components

All these components will receive data from the selected period instead of "latest metrics":

- ScoreCard
- DimensionChart
- EVMSection
- QualityMetricsGrid
- DORASection

No changes needed to these components themselves - they receive data via props from ProjectDetail.

### UI Dependencies

- Uses existing shadcn components (no external libraries)
- Slider built with `div` + CSS for markers
- Transitions with Tailwind (`transition-all`)

## Implementation Tasks

1. **Backend**: Add year/month query params to scores endpoint
2. **Frontend hooks**: Update `useProjectScores` and `useProjectMetrics` to accept optional period
3. **TimelineSlider component**: Create new component with marker rendering and interactions
4. **ProjectDetail integration**: Add state, pass to slider, pass period to hooks
5. **Empty state**: Add overlay and capture button when no data for selected period
6. **Testing**: Unit tests for slider, integration tests for period selection flow
