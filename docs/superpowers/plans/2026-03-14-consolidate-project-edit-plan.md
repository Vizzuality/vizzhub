# Consolidate Project Edit Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the duplicate scorecard ProjectForm and move EVM/Milestones editing into the core ProjectForm at `/projects/:id/edit`.

**Architecture:** New backend endpoint `PUT /projects/{project_id}/budget` handles EVM+Milestones upsert with auto-creation of metrics records. Core ProjectForm expands with Budget & Milestones sections. Scorecard detail becomes read-only for EVM/Milestones with an Edit link to the core form.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, React 18, TypeScript, react-hook-form, TanStack Query, shadcn/ui, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-14-consolidate-project-edit-design.md`

---

## File Structure

### Backend
- **Create:** `backend/tests/test_project_budget_api.py` — Tests for the new budget endpoint
- **Modify:** `backend/app/modules/scorecard/models/metrics/api_models.py` — Add `EVMDataPartial` with optional fields
- **Modify:** `backend/app/core/api/projects_v2.py` — Add `PUT /projects/{project_id}/budget` endpoint
- **Modify:** `backend/app/modules/scorecard/public.py` — Export `MetricsService`, `EVMDataPartial`, `Milestone`, `SnapshotType` for cross-module access

### Frontend — New files
- **Create:** `frontend/src/shared/utils/evmCalculations.ts` — Extracted EVM calculation helpers (SPI, CPI, EV, formatting)
- **Create:** `frontend/src/core/hooks/useProjectBudget.ts` — Hook for PUT /projects/{id}/budget + loading current metrics

### Frontend — Modified files
- **Modify:** `frontend/src/core/pages/ProjectForm.tsx` — Add Budget & Milestones sections, unified save
- **Modify:** `frontend/src/core/services/projects.ts` — Add `updateBudget()` API method
- **Modify:** `frontend/src/modules/scorecard/components/ProjectDetail/ProjectHeader.tsx` — Remove inline editing, Edit → Link
- **Modify:** `frontend/src/modules/scorecard/components/ProjectDetail/StatusControls.tsx` — Edit button → Link to `/projects/:id/edit`
- **Modify:** `frontend/src/modules/scorecard/components/ProjectDetail/EVMSection.tsx` — Remove all editing, read-only only
- **Modify:** `frontend/src/modules/scorecard/pages/ProjectDetail.tsx` — Remove editing state/hooks for project & EVM/Milestones
- **Modify:** `frontend/src/modules/scorecard/pages/Projects.tsx` — Create button → navigate to `/projects/new`

### Frontend — Delete
- **Delete:** `frontend/src/modules/scorecard/components/Forms/ProjectForm.tsx`

---

## Task 1: Backend — EVMDataPartial schema

**Files:**
- Modify: `backend/app/modules/scorecard/models/metrics/api_models.py`
- Modify: `backend/app/modules/scorecard/models/metrics/__init__.py` (if needed for export)

The current `EVMData` requires all 4 fields. We need a partial version where all fields are optional (budget can exist without cost/progress).

- [ ] **Step 1: Add EVMDataPartial model**

In `backend/app/modules/scorecard/models/metrics/api_models.py`, add after the existing `EVMData` class:

```python
class EVMDataPartial(BaseModel):
    """EVM data with all fields optional — for project budget endpoint."""

    budget_total: float | None = Field(default=None, ge=0, description="Planned Value total (PV)")
    cost_to_date: float | None = Field(default=None, ge=0, description="Actual Cost (AC)")
    percent_completed: float | None = Field(
        default=None, ge=0, le=1, description="Completion ratio 0-1"
    )
    percent_planned: float | None = Field(
        default=None, ge=0, le=1, description="Planned progress ratio 0-1"
    )

    def to_evm_dict(self) -> dict:
        """Return only non-None fields as a flat dict for DB update."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
```

- [ ] **Step 2: Export from metrics package**

Ensure `EVMDataPartial` is exported from `backend/app/modules/scorecard/models/metrics/__init__.py` alongside `EVMData`.

- [ ] **Step 3: Verify import works**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -c "from app.modules.scorecard.models.metrics import EVMDataPartial; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/scorecard/models/metrics/api_models.py backend/app/modules/scorecard/models/metrics/__init__.py
git commit -m "feat: add EVMDataPartial schema with optional fields for budget endpoint"
```

---

## Task 2: Backend — Budget endpoint + tests

**Files:**
- Create: `backend/tests/test_project_budget_api.py`
- Modify: `backend/app/core/api/projects_v2.py`
- Modify: `backend/app/modules/scorecard/public.py`

- [ ] **Step 1: Update scorecard public.py for cross-module access**

The budget endpoint lives in `core/api/` but needs scorecard's `MetricsService`. Per architecture rules, cross-module imports go through `public.py`.

In `backend/app/modules/scorecard/public.py`:

```python
"""Public interface for the scorecard module.

Other modules should import from here, never from scorecard internals.
"""

from app.modules.scorecard.models.metrics import EVMDataPartial, SnapshotType
from app.modules.scorecard.models.metrics.embedded import Milestone
from app.modules.scorecard.services.metrics_service import MetricsService

__all__ = ["EVMDataPartial", "MetricsService", "Milestone", "SnapshotType"]
```

- [ ] **Step 2: Write the tests**

Create `backend/tests/test_project_budget_api.py`:

```python
"""Tests for PUT /projects/{project_id}/budget endpoint."""

from datetime import date

import pytest
from httpx import AsyncClient


@pytest.fixture
def _current_period() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


class TestProjectBudgetUpdate:
    """Tests for PUT /api/projects/{project_id}/budget."""

    @pytest.mark.asyncio
    async def test_update_budget_creates_metrics_if_none_exist(
        self, client: AsyncClient, sample_project, _current_period
    ) -> None:
        """Budget update auto-creates metrics record for current period."""
        year, month = _current_period
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={
                "evm_data": {
                    "budget_total": 100000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evm_data"]["budget_total"] == 100000
        assert data["period_year"] == year
        assert data["period_month"] == month

    @pytest.mark.asyncio
    async def test_update_budget_partial_evm(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update accepts partial EVM data (budget_total only)."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={
                "evm_data": {
                    "budget_total": 50000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evm_data"]["budget_total"] == 50000
        assert data["evm_data"]["cost_to_date"] is None

    @pytest.mark.asyncio
    async def test_update_budget_full_evm(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update with all EVM fields."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={
                "evm_data": {
                    "budget_total": 100000,
                    "cost_to_date": 45000,
                    "percent_completed": 0.5,
                    "percent_planned": 0.45,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evm_data"]["budget_total"] == 100000
        assert data["evm_data"]["cost_to_date"] == 45000

    @pytest.mark.asyncio
    async def test_update_budget_milestones(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update with milestones."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={
                "milestones": [
                    {"name": "MVP", "planned_date": "2026-06-01"},
                    {"name": "Launch", "planned_date": "2026-09-01", "actual_date": "2026-09-05"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["milestones"]) == 2
        assert data["milestones"][0]["name"] == "MVP"

    @pytest.mark.asyncio
    async def test_update_budget_evm_and_milestones(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update with both EVM and milestones."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={
                "evm_data": {"budget_total": 200000},
                "milestones": [{"name": "Phase 1", "planned_date": "2026-04-01"}],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evm_data"]["budget_total"] == 200000
        assert len(data["milestones"]) == 1

    @pytest.mark.asyncio
    async def test_update_budget_preserves_existing_metrics(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Second budget update preserves previously set fields."""
        await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={"evm_data": {"budget_total": 100000}},
        )
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={"evm_data": {"cost_to_date": 30000}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evm_data"]["budget_total"] == 100000
        assert data["evm_data"]["cost_to_date"] == 30000

    @pytest.mark.asyncio
    async def test_update_budget_empty_body(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update with empty body is a no-op."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_budget_nonexistent_project(
        self, client: AsyncClient
    ) -> None:
        """Budget update for nonexistent project returns 404."""
        response = await client.put(
            "/api/projects/00000000-0000-0000-0000-000000000000/budget",
            json={"evm_data": {"budget_total": 50000}},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_budget_invalid_evm_values(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update rejects negative values."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={"evm_data": {"budget_total": -1000}},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_budget_percent_out_of_range(
        self, client: AsyncClient, sample_project
    ) -> None:
        """Budget update rejects percent > 1."""
        response = await client.put(
            f"/api/projects/{sample_project.id}/budget",
            json={"evm_data": {"percent_completed": 1.5}},
        )
        assert response.status_code == 422
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -m pytest tests/test_project_budget_api.py -v`
Expected: FAIL (endpoint doesn't exist yet)

- [ ] **Step 4: Implement the budget endpoint**

In `backend/app/core/api/projects_v2.py`, add at the top imports:

```python
from datetime import date
from app.config import get_scoring_config
from app.modules.scorecard.public import EVMDataPartial, MetricsService, Milestone, SnapshotType
```

Add Pydantic schema (at module level, before the router functions):

```python
from pydantic import BaseModel

class ProjectBudgetUpdate(BaseModel):
    evm_data: EVMDataPartial | None = None
    milestones: list[Milestone] | None = None
```

Add endpoint:

```python
@router.put("/{project_id}/budget")
@limiter.limit("60/minute")
async def update_project_budget(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    project_id: UUID,
    payload: ProjectBudgetUpdate,
    cache: OptionalScoreCache,
) -> dict:
    """Update EVM budget data and milestones for current period.

    Auto-creates metrics record if none exists for the current period.
    """
    project = await db.get(ProjectDB, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    today = date.today()
    year, month = today.year, today.month
    config = get_scoring_config()

    data: dict = {}
    if payload.evm_data:
        data.update(payload.evm_data.to_evm_dict())
    if payload.milestones is not None:
        data["milestones"] = [m.model_dump(mode="json") for m in payload.milestones]

    if not data:
        existing = await MetricsService.get_metrics(db, str(project_id), year, month)
        if existing:
            return _metrics_to_budget_response(existing[0], year, month)
        return {"period_year": year, "period_month": month, "evm_data": {}, "milestones": []}

    metrics = await MetricsService.upsert_metrics(
        db, project_id, year, month, SnapshotType.CUMULATIVE, config, data
    )

    if cache:
        await cache.invalidate(str(project_id))

    return _metrics_to_budget_response(metrics, year, month)


def _metrics_to_budget_response(metrics, year: int, month: int) -> dict:
    """Build budget response from metrics DB record."""
    evm_data = {
        "budget_total": metrics.budget_total,
        "cost_to_date": metrics.cost_to_date,
        "percent_completed": metrics.percent_completed,
        "percent_planned": metrics.percent_planned,
    }
    milestones = metrics.milestones if metrics.milestones else []
    return {
        "period_year": year,
        "period_month": month,
        "evm_data": evm_data,
        "milestones": milestones,
    }
```

Note: `OptionalScoreCache` dependency must be imported — check existing imports in the file. Also import `UUID` from `uuid` if not already imported.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -m pytest tests/test_project_budget_api.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Run full backend tests to check for regressions**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -m pytest --timeout=30 -x -q`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/scorecard/public.py backend/app/core/api/projects_v2.py backend/tests/test_project_budget_api.py
git commit -m "feat: add PUT /projects/{id}/budget endpoint for EVM and milestones upsert"
```

---

## Task 3: Frontend — Extract EVM calculation helpers

**Files:**
- Create: `frontend/src/shared/utils/evmCalculations.ts`

Extract calculation logic from `EVMForm.tsx` to a shared utility so both the scorecard EVMSection (read-only) and the core ProjectForm can use it without cross-module imports.

- [ ] **Step 1: Create shared utility**

Create `frontend/src/shared/utils/evmCalculations.ts`:

```typescript
export interface EVMCalculatedValues {
  ev: number;
  spi: number | null;
  cpi: number | null;
  hasData: boolean;
}

export function calculateEVMValues(
  budgetTotal: number,
  costToDate: number,
  percentCompleted: number,
  percentPlanned: number,
): EVMCalculatedValues {
  const ev = budgetTotal * percentCompleted;
  const spi = percentPlanned > 0 ? percentCompleted / percentPlanned : null;
  const cpi = costToDate > 0 ? ev / costToDate : null;
  return { ev, spi, cpi, hasData: budgetTotal > 0 };
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function getPerformanceColor(value: number): string {
  if (value >= 1) return 'text-score-green';
  if (value >= 0.9) return 'text-score-yellow';
  return 'text-score-red';
}

export function getPerformanceLabel(value: number, metric: 'spi' | 'cpi'): string {
  if (metric === 'spi') {
    if (value > 1) return 'Ahead of schedule';
    if (value === 1) return 'On schedule';
    return 'Behind schedule';
  }
  if (value > 1) return 'Under budget';
  if (value === 1) return 'On budget';
  return 'Over budget';
}
```

- [ ] **Step 2: Update EVMForm.tsx to use shared helpers**

In `frontend/src/modules/scorecard/components/Forms/EVMForm.tsx`:
- Remove local `formatCurrency`, `getPerformanceColor`, `getPerformanceLabel` functions
- Add import: `import { formatCurrency, getPerformanceColor, getPerformanceLabel } from '@/shared/utils/evmCalculations';`

- [ ] **Step 3: Run frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared/utils/evmCalculations.ts frontend/src/modules/scorecard/components/Forms/EVMForm.tsx
git commit -m "refactor: extract EVM calculation helpers to shared utility"
```

---

## Task 4: Frontend — Budget API service and hook

**Files:**
- Modify: `frontend/src/core/services/projects.ts` — Add `updateBudget()` method
- Create: `frontend/src/core/hooks/useProjectBudget.ts` — Hook for fetching + updating budget

- [ ] **Step 1: Add budget API method to projects service**

In `frontend/src/core/services/projects.ts`, add to `projectsApi`:

```typescript
updateBudget: async (projectId: string, data: {
  evm_data?: {
    budget_total?: number;
    cost_to_date?: number;
    percent_completed?: number;
    percent_planned?: number;
  };
  milestones?: Array<{
    name: string;
    planned_date: string;
    actual_date?: string;
  }>;
}): Promise<{
  period_year: number;
  period_month: number;
  evm_data: {
    budget_total: number | null;
    cost_to_date: number | null;
    percent_completed: number | null;
    percent_planned: number | null;
  };
  milestones: Array<{
    name: string;
    planned_date: string;
    actual_date?: string;
  }>;
}> => {
  const response = await client.put(`/projects/${projectId}/budget`, data);
  return response.data;
},
```

- [ ] **Step 2: Create budget hook**

Create `frontend/src/core/hooks/useProjectBudget.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/core/services/projects';
import { queryKeys } from '@/core/hooks/queryKeys';

interface EVMFormData {
  budget_total: string;
  cost_to_date: string;
  percent_completed: string;
  percent_planned: string;
}

interface MilestoneFormData {
  name: string;
  planned_date: string;
  actual_date: string;
}

interface BudgetPayload {
  evm_data?: {
    budget_total?: number;
    cost_to_date?: number;
    percent_completed?: number;
    percent_planned?: number;
  };
  milestones?: Array<{
    name: string;
    planned_date: string;
    actual_date?: string;
  }>;
}

export function buildBudgetPayload(
  evm: EVMFormData,
  milestones: MilestoneFormData[],
): BudgetPayload | null {
  const payload: BudgetPayload = {};

  const evmFields: Record<string, number> = {};
  if (evm.budget_total) evmFields.budget_total = Number.parseFloat(evm.budget_total);
  if (evm.cost_to_date) evmFields.cost_to_date = Number.parseFloat(evm.cost_to_date);
  if (evm.percent_completed) evmFields.percent_completed = Number.parseFloat(evm.percent_completed) / 100;
  if (evm.percent_planned) evmFields.percent_planned = Number.parseFloat(evm.percent_planned) / 100;

  if (Object.keys(evmFields).length > 0) {
    payload.evm_data = evmFields;
  }

  const validMilestones = milestones
    .filter((m) => m.name && m.planned_date)
    .map((m) => ({
      name: m.name,
      planned_date: m.planned_date,
      actual_date: m.actual_date || undefined,
    }));

  if (validMilestones.length > 0) {
    payload.milestones = validMilestones;
  }

  if (!payload.evm_data && !payload.milestones) return null;
  return payload;
}

export function useCurrentPeriodMetrics(projectId: string) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  return useQuery({
    queryKey: queryKeys.metrics.byPeriod(projectId, year, month),
    queryFn: async () => {
      try {
        const { metricsHistoryApi } = await import('@/modules/scorecard/services/metrics');
        return await metricsHistoryApi.getByPeriod(projectId, year, month);
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}

export function useUpdateProjectBudget(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BudgetPayload) => projectsApi.updateBudget(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
    },
  });
}
```

- [ ] **Step 3: Run frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/services/projects.ts frontend/src/core/hooks/useProjectBudget.ts
git commit -m "feat: add budget API service and useProjectBudget hook"
```

---

## Task 5: Frontend — Expand ProjectForm with Budget & Milestones

**Files:**
- Modify: `frontend/src/core/pages/ProjectForm.tsx`

This is the largest task. Add EVM and Milestones sections to the existing form with a unified save.

- [ ] **Step 1: Add imports**

At the top of `frontend/src/core/pages/ProjectForm.tsx`, add:

```typescript
import { Plus, Trash2 as TrashMilestone } from 'lucide-react';
import { useFieldArray } from 'react-hook-form';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { Info, Calculator, DollarSign, TrendingUp, Clock } from 'lucide-react';
import {
  calculateEVMValues,
  formatCurrency,
  getPerformanceColor,
  getPerformanceLabel,
} from '@/shared/utils/evmCalculations';
import {
  useCurrentPeriodMetrics,
  useUpdateProjectBudget,
  buildBudgetPayload,
} from '@/core/hooks/useProjectBudget';
```

Note: `Trash2` is already imported — rename the milestones one to `TrashMilestone` or use the same icon.

- [ ] **Step 2: Extend form data type**

Update the `ProjectFormData` interface to include EVM and milestones:

```typescript
interface ProjectFormData {
  name: string;
  code: string;
  status: ProjectStatus;
  currency: string;
  program_id: string;
  jira_project_key: string;
  github_repo: string;
  start_date: string;
  end_date: string;
  notes: string;
  summary: string;
  budget_total: string;
  cost_to_date: string;
  percent_completed: string;
  percent_planned: string;
  milestones: { name: string; planned_date: string; actual_date: string }[];
}
```

- [ ] **Step 3: Initialize form with metrics data**

In the component, after the existing `useProject` call, add the metrics query:

```typescript
const { data: currentMetrics } = useCurrentPeriodMetrics(id ?? '');
const budgetMutation = useUpdateProjectBudget(id ?? '');
```

Update `defaultValues` to include:

```typescript
defaultValues: {
  // ... existing fields ...
  budget_total: '',
  cost_to_date: '',
  percent_completed: '',
  percent_planned: '',
  milestones: [{ name: '', planned_date: '', actual_date: '' }],
},
```

In the `if (isEditMode && project && !formInitialized)` block, add after existing fields:

```typescript
// Budget & milestones from current period metrics
if (currentMetrics) {
  const evm = currentMetrics.evm_data;
  if (evm) {
    reset({
      ...getValues(),
      budget_total: evm.budget_total?.toString() ?? '',
      cost_to_date: evm.cost_to_date?.toString() ?? '',
      percent_completed: evm.percent_completed ? (evm.percent_completed * 100).toString() : '',
      percent_planned: evm.percent_planned ? (evm.percent_planned * 100).toString() : '',
    });
  }
  if (currentMetrics.milestones?.length) {
    reset({
      ...getValues(),
      milestones: currentMetrics.milestones.map((m) => ({
        name: m.name,
        planned_date: m.planned_date,
        actual_date: m.actual_date ?? '',
      })),
    });
  }
}
```

Wait for `currentMetrics` to be loaded before setting `formInitialized`:

```typescript
if (isEditMode && project && !formInitialized && (currentMetrics !== undefined)) {
```

Add `useFieldArray` for milestones:

```typescript
const { fields: milestoneFields, append: appendMilestone, remove: removeMilestone } = useFieldArray({
  control,
  name: 'milestones',
});
```

Note: Need to destructure `control` and `getValues` from `useForm` (add to existing destructure).

- [ ] **Step 4: Add EVM calculated values preview**

Add a `useMemo` for EVM calculated values:

```typescript
const evmPreview = useMemo(() => {
  const budget = Number.parseFloat(watchedBudgetTotal) || 0;
  const cost = Number.parseFloat(watchedCostToDate) || 0;
  const completed = (Number.parseFloat(watchedPercentCompleted) || 0) / 100;
  const planned = (Number.parseFloat(watchedPercentPlanned) || 0) / 100;
  return calculateEVMValues(budget, cost, completed, planned);
}, [watchedBudgetTotal, watchedCostToDate, watchedPercentCompleted, watchedPercentPlanned]);
```

Where the watched values come from `watch()`:

```typescript
const watchedBudgetTotal = watch('budget_total');
const watchedCostToDate = watch('cost_to_date');
const watchedPercentCompleted = watch('percent_completed');
const watchedPercentPlanned = watch('percent_planned');
```

- [ ] **Step 5: Update handleFormSubmit for unified save**

Replace the existing `handleFormSubmit` to handle both project + budget in one save:

```typescript
const handleFormSubmit = async (data: ProjectFormData): Promise<void> => {
  setApiError(null);

  const projectPayload: ProjectCreate = {
    name: data.name,
    code: data.code,
    status: data.status,
    is_billable: isBillable,
    has_scorecard: hasScorecard,
    has_dependabot_alerts: hasDependabotAlerts,
    has_budget_alerts: hasBudgetAlerts,
    currency: data.currency || null,
    program_id: data.program_id || null,
    jira_project_key: data.jira_project_key || undefined,
    github_repo: data.github_repo || undefined,
    slack_channel_id: slackChannelId || undefined,
    start_date: data.start_date?.trim() || undefined,
    end_date: data.end_date?.trim() || undefined,
    notes: data.notes?.trim() || null,
    summary: data.summary?.trim() || null,
  };

  const budgetPayload = buildBudgetPayload(
    {
      budget_total: data.budget_total,
      cost_to_date: data.cost_to_date,
      percent_completed: data.percent_completed,
      percent_planned: data.percent_planned,
    },
    data.milestones,
  );

  try {
    if (isEditMode) {
      const promises: Promise<unknown>[] = [replaceMutation.mutateAsync(projectPayload)];
      if (budgetPayload) {
        promises.push(budgetMutation.mutateAsync(budgetPayload));
      }
      await Promise.all(promises);
    } else {
      const newProject = await createMutation.mutateAsync(projectPayload);
      if (budgetPayload && newProject?.id) {
        await projectsApi.updateBudget(newProject.id, budgetPayload);
      }
    }
    navigateToProjects();
  } catch (error) {
    setApiError(getApiErrorMessage(error));
  }
};
```

Note: `createMutation.mutateAsync` must return the created project with its `id`. Check that `projectsApi.create` returns the full project response. If not, update the service to return it.

- [ ] **Step 6: Add Budget & Schedule section JSX**

After the Summary textarea section and before the submit buttons, add:

```tsx
{/* Budget & Schedule */}
<div className="space-y-4 pt-4 border-t">
  <h3 className="text-lg font-medium">Budget & Schedule</h3>
  <TooltipProvider>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-muted-foreground" />
          <Label htmlFor="budget_total">Total Budget</Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="text-muted-foreground hover:text-foreground">
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">The total planned budget for the entire project</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <Input
          id="budget_total"
          type="number"
          step="any"
          min="0"
          placeholder="e.g., 100000"
          {...register('budget_total', {
            min: { value: 0, message: 'Must be positive' },
          })}
        />
        {errors.budget_total && (
          <p className="text-sm text-destructive">{errors.budget_total.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-muted-foreground" />
          <Label htmlFor="cost_to_date">Actual Cost</Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="text-muted-foreground hover:text-foreground">
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">The actual expenses incurred to date</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <Input
          id="cost_to_date"
          type="number"
          step="any"
          min="0"
          placeholder="e.g., 45000"
          {...register('cost_to_date', {
            min: { value: 0, message: 'Must be positive' },
          })}
        />
        {errors.cost_to_date && (
          <p className="text-sm text-destructive">{errors.cost_to_date.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-muted-foreground" />
          <Label htmlFor="percent_completed">Work Completed</Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="text-muted-foreground hover:text-foreground">
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">Percentage of total work completed (0-100%)</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <div className="relative">
          <Input
            id="percent_completed"
            type="number"
            step="any"
            min="0"
            max="100"
            placeholder="e.g., 50"
            {...register('percent_completed', {
              min: { value: 0, message: 'Must be 0-100' },
              max: { value: 100, message: 'Must be 0-100' },
            })}
            className="pr-8"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
        </div>
        {errors.percent_completed && (
          <p className="text-sm text-destructive">{errors.percent_completed.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-muted-foreground" />
          <Label htmlFor="percent_planned">Expected Progress</Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="text-muted-foreground hover:text-foreground">
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">Expected progress percentage according to schedule (0-100%)</p>
            </TooltipContent>
          </Tooltip>
        </div>
        <div className="relative">
          <Input
            id="percent_planned"
            type="number"
            step="any"
            min="0"
            max="100"
            placeholder="e.g., 45"
            {...register('percent_planned', {
              min: { value: 0, message: 'Must be 0-100' },
              max: { value: 100, message: 'Must be 0-100' },
            })}
            className="pr-8"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
        </div>
        {errors.percent_planned && (
          <p className="text-sm text-destructive">{errors.percent_planned.message}</p>
        )}
      </div>
    </div>
  </TooltipProvider>

  {/* Calculated Values Preview */}
  {evmPreview.hasData && (
    <Card className="bg-muted/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Calculator className="w-4 h-4" />
          Calculated Values
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 bg-background rounded-lg">
            <p className="text-xs text-muted-foreground mb-1">Earned Value (EV)</p>
            <p className="text-lg font-semibold">{formatCurrency(evmPreview.ev)}</p>
          </div>
          <div className="p-3 bg-background rounded-lg">
            <p className="text-xs text-muted-foreground mb-1">Schedule Performance (SPI)</p>
            {evmPreview.spi !== null ? (
              <>
                <p className={`text-lg font-semibold ${getPerformanceColor(evmPreview.spi)}`}>
                  {evmPreview.spi.toFixed(2)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {getPerformanceLabel(evmPreview.spi, 'spi')}
                </p>
              </>
            ) : (
              <p className="text-lg font-semibold text-muted-foreground">&mdash;</p>
            )}
          </div>
          <div className="p-3 bg-background rounded-lg">
            <p className="text-xs text-muted-foreground mb-1">Cost Performance (CPI)</p>
            {evmPreview.cpi !== null ? (
              <>
                <p className={`text-lg font-semibold ${getPerformanceColor(evmPreview.cpi)}`}>
                  {evmPreview.cpi.toFixed(2)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {getPerformanceLabel(evmPreview.cpi, 'cpi')}
                </p>
              </>
            ) : (
              <p className="text-lg font-semibold text-muted-foreground">&mdash;</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )}
</div>
```

- [ ] **Step 7: Add Milestones section JSX**

After the Budget & Schedule section:

```tsx
{/* Milestones */}
<div className="space-y-4 pt-4 border-t">
  <h3 className="text-lg font-medium">Milestones</h3>
  <div className="space-y-3">
    {milestoneFields.map((field, index) => (
      <div
        key={field.id}
        className="grid grid-cols-[1fr_140px_140px_40px] gap-3 items-end p-3 bg-muted/50 rounded-lg"
      >
        <div className="space-y-1">
          {index === 0 && (
            <Label className="text-xs">Milestone Name</Label>
          )}
          <Input
            {...register(`milestones.${index}.name`)}
            placeholder="e.g., MVP Release"
          />
        </div>
        <div className="space-y-1">
          {index === 0 && (
            <Label className="text-xs">Planned</Label>
          )}
          <Input type="date" {...register(`milestones.${index}.planned_date`)} />
        </div>
        <div className="space-y-1">
          {index === 0 && (
            <Label className="text-xs">Actual</Label>
          )}
          <Input type="date" {...register(`milestones.${index}.actual_date`)} />
        </div>
        <div className={index === 0 ? 'pt-5' : ''}>
          {milestoneFields.length > 1 && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => removeMilestone(index)}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    ))}
  </div>
  <Button
    type="button"
    variant="outline"
    size="sm"
    onClick={() => appendMilestone({ name: '', planned_date: '', actual_date: '' })}
    className="w-full"
  >
    <Plus className="w-4 h-4 mr-2" />
    Add Milestone
  </Button>
</div>
```

- [ ] **Step 8: Update isMutating to include budget mutation**

```typescript
const isMutating = createMutation.isPending || replaceMutation.isPending || budgetMutation.isPending;
```

- [ ] **Step 9: Manual test in browser**

1. Start backend: `cd /Volumes/Work/Dev/vizzhub/backend && python run_server.py`
2. Start frontend: `cd /Volumes/Work/Dev/vizzhub/frontend && npm run dev`
3. Navigate to `/projects/new` — verify Budget & Milestones sections visible
4. Navigate to `/projects/:id/edit` — verify existing EVM data loads
5. Edit budget, add milestones, save — verify unified save works

- [ ] **Step 10: Run frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 11: Commit**

```bash
git add frontend/src/core/pages/ProjectForm.tsx
git commit -m "feat: add Budget & Milestones sections to core ProjectForm with unified save"
```

---

## Task 6: Frontend — Scorecard detail: Edit → Navigate + EVMSection read-only

**Files:**
- Modify: `frontend/src/modules/scorecard/components/ProjectDetail/StatusControls.tsx`
- Modify: `frontend/src/modules/scorecard/components/ProjectDetail/ProjectHeader.tsx`
- Modify: `frontend/src/modules/scorecard/components/ProjectDetail/EVMSection.tsx`
- Modify: `frontend/src/modules/scorecard/pages/ProjectDetail.tsx`

- [ ] **Step 1: StatusControls — Edit becomes Link**

Replace `StatusControls.tsx` content. Change `onEdit` prop to `projectId` prop:

```typescript
import { Link } from 'react-router-dom';
import { Pencil } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

interface StatusControlsProps {
  readonly projectId: string;
}

export default function StatusControls({ projectId }: StatusControlsProps): JSX.Element {
  return (
    <Button variant="ghost" size="sm" className="border border-input" asChild>
      <Link to={`/projects/${projectId}/edit`}>
        <Pencil className="w-4 h-4 mr-2" />
        Edit
      </Link>
    </Button>
  );
}
```

- [ ] **Step 2: ProjectHeader — Remove inline editing**

Simplify `ProjectHeader.tsx`:
- Remove imports: `ProjectForm`, `ProjectCreate`
- Remove props: `isEditing`, `onEdit`, `onCancelEdit`, `onSubmitEdit`, `isSubmitting`
- Add `project.id` to `StatusControls`:

```typescript
interface ProjectHeaderProps {
  project: Project;
  onMarkFinished: () => void;
  onReopen: () => Promise<unknown>;
  onDelete: () => void;
  isUpdatingStatus: boolean;
}
```

In the JSX, replace the conditional `{!isEditing && <StatusControls onEdit={onEdit} />}` with:

```tsx
<StatusControls projectId={project.id} />
```

Remove the `{isEditing && <CardContent>...</CardContent>}` block entirely.

- [ ] **Step 3: EVMSection — Remove all editing**

In `EVMSection.tsx`:

Remove imports: `useState`, `useRef`, `useCallback`, `Pencil`, `Button`, `AlertDialog*`, `EVMForm`
Remove props: `onUpdateEVM`, `onUpdateMilestones`, `isUpdatingEVM`, `isUpdatingMilestones`
Remove all state: `isEditingEVM`, `isEditingMilestones`, `hasMilestoneChanges`, `showDiscardAlert`, `pendingMilestonesRef`
Remove all handlers: `handleCloseEditing`, `handleUpdateEVM`, `handleCancelEditing`, `handleSaveMilestonesAndClose`, `handleDiscardAndClose`, `handleUpdateMilestones`, `handleMilestonesDirtyChange`, `handleMilestonesValuesChange`, `handleDeleteMilestone`
Remove the `AlertDialog` at the bottom

Updated interface:

```typescript
interface EVMSectionProps {
  readonly projectId: string;
  readonly evmData?: EVMData | null;
  readonly milestones?: Milestone[] | null;
  readonly indicators: Indicators;
  readonly getTarget: (name: string) => number | null;
  readonly getConstant: (name: string) => number | null;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
}
```

Replace the edit button with a Link:

```tsx
import { Link } from 'react-router-dom';
import { Pencil } from 'lucide-react';

// In the header area, replace the Edit button:
<Button variant="ghost" size="sm" className="border border-input" asChild>
  <Link to={`/projects/${projectId}/edit`}>
    <Pencil className="w-4 h-4 mr-2" />
    {evmData ? 'Edit' : 'Add Budget Data'}
  </Link>
</Button>
```

In the Card content, remove the editing branch. Keep only:

```tsx
<Card className="mb-6">
  <CardContent className="pt-6">
    {evmData ? (
      <EVMDataGrid evmData={evmData} />
    ) : (
      <p className="text-muted-foreground">
        No budget data available.{' '}
        <Link to={`/projects/${projectId}/edit`} className="text-primary hover:underline">
          Edit project
        </Link>{' '}
        to add budget and schedule information.
      </p>
    )}
  </CardContent>
</Card>
```

For the milestones display (currently inside the editing branch), move the read-only `MilestonesList` rendering outside. `MilestonesList` with `isEditing={false}` already renders read-only. Simplify its props:

```tsx
{milestones && milestones.length > 0 && (
  <Card className="mb-6">
    <CardContent className="pt-6">
      <MilestonesList
        milestones={milestones}
        isEditing={false}
        isLoading={false}
        onEdit={() => {}}
        onCancelEdit={() => {}}
        onSubmit={async () => {}}
        onDelete={async () => {}}
        getMilestoneStatus={getMilestoneStatus}
      />
    </CardContent>
  </Card>
)}
```

Note: `MilestonesList` still needs its props even in read-only mode. Keep the `getMilestoneStatus` function since it's used for display. Remove `handleDeleteMilestone` and pass a no-op.

- [ ] **Step 4: ProjectDetail.tsx — Remove editing state**

In `frontend/src/modules/scorecard/pages/ProjectDetail.tsx`:

Remove:
- `useState` for `isEditing`
- `useReplaceProject` import and usage
- `handleEdit` function
- `showDeleteConfirm` state (keep if delete is still accessible from status controls — check)
- `replaceProject` mutation

Simplify `ProjectHeader` props:

```tsx
<ProjectHeader
  project={project}
  onMarkFinished={() => setShowFinishDialog(true)}
  onReopen={() => updateProjectStatus.mutateAsync({ status: 'live' })}
  onDelete={() => setShowDeleteConfirm(true)}
  isUpdatingStatus={updateProjectStatus.isPending}
/>
```

Remove EVM/Milestones mutation hooks:
- `useUpdateEVMData` — remove
- `useUpdateMilestones` — remove
- `handleUpdateEVM` — remove
- `handleUpdateMilestones` — remove

Simplify `EVMSection` props:

```tsx
<EVMSection
  projectId={id!}
  evmData={metrics?.evm_data}
  milestones={metrics?.milestones}
  indicators={scores.indicators}
  getTarget={getTarget}
  getConstant={getConstant}
  snapshots={snapshots}
  visibleDimensions={visibleDimensions}
/>
```

Remove the `withHistoricalWarning` wrapper from EVM/milestones calls (it's still used by other metric cards).

- [ ] **Step 5: Run frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All tests pass (some scorecard tests may need updates)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/modules/scorecard/components/ProjectDetail/StatusControls.tsx \
  frontend/src/modules/scorecard/components/ProjectDetail/ProjectHeader.tsx \
  frontend/src/modules/scorecard/components/ProjectDetail/EVMSection.tsx \
  frontend/src/modules/scorecard/pages/ProjectDetail.tsx
git commit -m "refactor: make scorecard detail read-only for EVM/Milestones, Edit navigates to /projects/:id/edit"
```

---

## Task 7: Frontend — Delete scorecard ProjectForm + update scorecard Projects page

**Files:**
- Delete: `frontend/src/modules/scorecard/components/Forms/ProjectForm.tsx`
- Modify: `frontend/src/modules/scorecard/pages/Projects.tsx`

- [ ] **Step 1: Update scorecard Projects page**

In `frontend/src/modules/scorecard/pages/Projects.tsx`:

Remove `ProjectForm` import. Remove `showForm` state. Replace "Create" button to navigate to `/projects/new`:

```tsx
import { useNavigate } from 'react-router-dom';

// In component:
const navigate = useNavigate();

// Replace <Button onClick={() => setShowForm(true)}> with:
<Button onClick={() => navigate('/projects/new')}>
  Create Project
</Button>
```

Remove the `{showForm && <Card>...<ProjectForm />...</Card>}` block entirely.

Remove `useCreateProject` import and `createProject` mutation if it's only used by the inline form.

Remove `handleCreate` function.

- [ ] **Step 2: Delete scorecard ProjectForm**

Delete `frontend/src/modules/scorecard/components/Forms/ProjectForm.tsx`.

- [ ] **Step 3: Verify no remaining imports**

Run: `grep -r "Forms/ProjectForm" frontend/src/` — should return nothing.

- [ ] **Step 4: Run frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All tests pass. Fix any tests that reference the deleted form.

- [ ] **Step 5: Commit**

```bash
git rm frontend/src/modules/scorecard/components/Forms/ProjectForm.tsx
git add frontend/src/modules/scorecard/pages/Projects.tsx
git commit -m "refactor: remove scorecard ProjectForm, create button navigates to /projects/new"
```

---

## Task 8: Fix tests + full verification

**Files:**
- Modify: any test files that break due to the changes

- [ ] **Step 1: Run full backend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -m pytest --timeout=30 -x -q`
Expected: All pass. Fix any failures.

- [ ] **Step 2: Run full frontend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/frontend && npx vitest run --reporter=verbose 2>&1 | tail -30`
Expected: All pass. Fix any failures related to removed components/props.

- [ ] **Step 3: Manual end-to-end verification**

1. `/projects/new` — Budget & Milestones visible, create with budget data works
2. `/projects/:id/edit` — EVM data loads from current period, save updates both project + budget
3. `/scorecard/:id` — Edit button navigates to `/projects/:id/edit`
4. `/scorecard/:id` — EVM section is read-only, shows "Edit project" link when no data
5. `/scorecard` — Create button navigates to `/projects/new`

- [ ] **Step 4: Commit any test fixes**

```bash
git add -A
git commit -m "fix: update tests for consolidated project edit"
```
