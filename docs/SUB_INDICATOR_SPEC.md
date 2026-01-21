# Sub-Indicator Card Specification

Pattern for implementing sub-indicator cards that display metrics with KPI targets.

## Architecture Overview

```
Backend                                      Frontend
────────────────────────────────────────────────────────────────────────
Collector Module          →  Raw Metrics    →  useProjectMetrics hook
  (JQL queries)              (jira_defects)

Normalizer/Calculator     →  Indicator      →  useProjectScores hook
  (formula)                  (0-100 scale)

Config DB                 →  Target (KPI)   →  useConfigParameters hook
  (Targets category)

                                            →  SubIndicatorCard component
```

## Backend Implementation

### 1. Collector Module

Location: `backend/app/services/collectors/jira/<indicator_name>.py`

```python
"""
<indicator_name> - Brief description

== SPEC ==

Formula:
    <indicator> = <formula>

JQL Queries:
    <query_name>: project = "KEY" AND <conditions>

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    <Target_t> from config DB (default: X)

Normalization:
    Lower/Higher is better: <normalization_formula>

Edge Cases:
    - <case>: <behavior>

== END SPEC ==
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_<indicator_name>(client: "JiraClient", project_key: str) -> dict:
    """Collect metrics from Jira."""
    metric_a = await client.count_issues(project_key, "<JQL query>")
    metric_b = await client.count_issues(project_key, "<JQL query>")

    return {
        "metric_a": metric_a,
        "metric_b": metric_b,
    }


def calculate_<indicator_name>(metric_a: int, metric_b: int) -> float | None:
    """Calculate indicator from raw counts."""
    if metric_b <= 0:
        return 0.0
    return (metric_a / metric_b) * 100
```

### 2. Model Fields

Location: `backend/app/models/metrics.py`

Add fields to the appropriate metrics class (e.g., `JiraDefectMetrics`, `FlowMetrics`):

```python
class JiraDefectMetrics(BaseModel):
    metric_a: int = Field(..., ge=0)
    metric_b: int = Field(..., ge=0)
```

### 3. Collector Integration

Location: `backend/app/services/collectors/jira/collector.py`

Import and call the collector function:

```python
from app.services.collectors.jira.<indicator_name> import collect_<indicator_name>

# In collect() method:
indicator_data = await collect_<indicator_name>(self._jira_client, project_key)
metrics.update(indicator_data)
```

### 4. API Response Mapping

Location: `backend/app/api/collectors.py`

Map raw metrics to database structure:

```python
jira_defects = {
    "metric_a": raw_metrics.get("metric_a", 0),
    "metric_b": raw_metrics.get("metric_b", 0),
}
```

### 5. Normalizer/Calculator

Location: `backend/app/services/normalizers/indicators.py`

Add calculation method:

```python
def _calculate_<indicator_name>(self, data: MetricsClass | None) -> float | None:
    if not data:
        return None
    if data.metric_b <= 0:
        return 0.0
    return (data.metric_a / data.metric_b) * 100
```

### 6. Config Target

Add target to config DB via Settings UI:
- Category: `Targets`
- Name: `<Indicator>_t` (e.g., `DefDensity_t`)
- Value: Target number

---

## Frontend Implementation

### 1. Types

Location: `frontend/src/types/index.ts`

Add to `MetricsCreate` interface:

```typescript
jira_defects?: {
  metric_a: number;
  metric_b: number;
};
```

Add to `Indicators` interface:

```typescript
indicator_name: number | null;
```

### 2. SubIndicatorCard Component

Location: `frontend/src/components/SubIndicatorCard/SubIndicatorCard.tsx`

Props interface:

```typescript
interface SubIndicatorCardProps {
  title: string;              // Card title (e.g., "Defect Density")
  indicatorValue: number | null;  // Calculated value from scores API
  indicatorLabel: string;     // Label for value (e.g., "Bugs per 100 tasks")
  indicatorSuffix?: string;   // Suffix for value (default: "%")
  metrics: MetricItem[];      // Raw metrics to display
  description?: string;       // Optional description under title
  target?: number | null;     // KPI target from config
  lowerIsBetter?: boolean;    // For color coding (default: true)
  formula?: string;           // Formula shown in tooltip
}

interface MetricItem {
  label: string;              // Metric label (e.g., "Bugs")
  value: number | string | null;
  suffix?: string;
}
```

### 3. Page Integration

Location: `frontend/src/pages/ProjectDetail.tsx`

```tsx
import SubIndicatorCard from '../components/SubIndicatorCard';
import { useConfigParameters } from '../hooks/useConfig';

// Inside component:
const { data: config } = useConfigParameters();

const getTarget = (name: string): number | null => {
  const targets = config?.['Targets'];
  if (!targets) return null;
  const param = targets.find((p) => p.name === name);
  return param ? parseFloat(param.value) : null;
};

// In JSX (inside Sub-indicators section):
<SubIndicatorCard
  title="Indicator Name"
  indicatorValue={scores.indicators.indicator_name}
  indicatorLabel="Description of value"
  indicatorSuffix="%"
  description="Brief explanation"
  target={getTarget('Indicator_t')}
  lowerIsBetter={true}
  formula="(A / B) × 100"
  metrics={[
    { label: 'Metric A', value: metrics.data_source.metric_a },
    { label: 'Metric B', value: metrics.data_source.metric_b },
  ]}
/>
```

---

## Visual Design

```
┌─────────────────────────────────────────┐
│ Title                              (i)  │  ← Info icon with formula tooltip
│ Description (muted)                     │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ Label                       VALUE%  │ │  ← Large, colored by target
│ │─────────────────────────────────────│ │
│ │ KPI                           ≤X%   │ │  ← Target from config
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────┐  ┌─────────────┐        │
│ │ Metric A    │  │ Metric B    │        │  ← Raw metrics grid
│ │       123   │  │       456   │        │
│ └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────┘
```

**Color coding:**
- Green: Value meets target (≤ target if lowerIsBetter, ≥ target otherwise)
- Red: Value exceeds target
- Default: No target configured

---

## Example: Defect Density

**Backend collector:** `defect_density.py`
- JQL: `type = Bug` (all bugs)
- JQL: `type in (Story, Task, Sub-task) AND statusCategory = Done` (completed tasks)
- Formula: `(bugs / tasks) × 100`

**Config target:** `DefDensity_t = 3`

**Frontend usage:**
```tsx
<SubIndicatorCard
  title="Defect Density"
  indicatorValue={scores.indicators.defect_density}
  indicatorLabel="Bugs per 100 tasks"
  indicatorSuffix="%"
  description="Ratio of bugs to completed tasks"
  target={getTarget('DefDensity_t')}
  lowerIsBetter={true}
  formula="(Bugs / Tasks) × 100"
  metrics={[
    { label: 'Bugs', value: metrics.jira_defects.bugs_total },
    { label: 'Tasks Completed', value: metrics.jira_defects.tasks_completed },
  ]}
/>
```

---

## Checklist for New Sub-Indicators

### Backend
- [ ] Create collector module with SPEC docstring
- [ ] Add fields to metrics model
- [ ] Integrate in main collector
- [ ] Map in API collectors endpoint
- [ ] Add calculation in normalizers
- [ ] Add target in config DB
- [ ] Write tests

### Frontend
- [ ] Add types to `index.ts`
- [ ] Add `SubIndicatorCard` to ProjectDetail
- [ ] Connect to scores, metrics, and config hooks
