# Projects UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a central Projects view with list, create, and edit pages, plus status enum migration.

**Architecture:** New `/api/projects` router in core (coexists with `/api/scorecards`). Frontend gets a new `/projects` route with its own pages, reusing patterns from scorecard. Status enum changes from `in_progress`/`finished` to `proposal`/`live`/`finished` across the whole platform.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic (backend); React, TypeScript, React Query, shadcn/ui, Tailwind (frontend)

**Spec:** `docs/plans/2026-03-14-projects-ui-design.md`

---

## File Map

### Backend — New files
- `backend/alembic/versions/020_status_enum_migration.py` — Alembic migration
- `backend/app/core/api/projects_v2.py` — New `/api/projects` router
- `backend/app/core/api/programs.py` — Programs list endpoint

### Backend — Modified files
- `backend/app/core/models/project.py` — Update `ProjectStatus` enum, `ProjectCreate` schema (code required), add `ProjectResponse` with program_name
- `backend/app/main.py` — Mount new routers
- `backend/app/core/api/projects.py` — Update status filter whitelist

### Frontend — New files
- `frontend/src/core/pages/Projects.tsx` — Projects index page
- `frontend/src/core/pages/ProjectForm.tsx` — Create/edit project page
- `frontend/src/core/components/ProjectCard.tsx` — Project card component
- `frontend/src/core/services/programs.ts` — Programs API service
- `frontend/src/core/hooks/usePrograms.ts` — Programs hook
- `frontend/src/core/hooks/useProjectListParams.ts` — URL state for projects list

### Frontend — Modified files
- `frontend/src/core/types/project.ts` — Add new fields, update status enum
- `frontend/src/core/services/projects.ts` — Add `/projects` API methods
- `frontend/src/core/hooks/queryKeys.ts` — Add programs keys
- `frontend/src/core/hooks/useProjects.ts` — Add hooks for new endpoints
- `frontend/src/core/components/layout/AppSidebar.tsx` — Add Projects item
- `frontend/src/App.tsx` — Add routes, change default redirect

---

## Task 1: Status Enum Migration (Backend)

**Files:**
- Modify: `backend/app/core/models/project.py`
- Create: `backend/alembic/versions/020_status_enum_migration.py`
- Modify: `backend/app/core/api/projects.py:57`

- [ ] **Step 1: Update ProjectStatus enum**

In `backend/app/core/models/project.py`, change:
```python
class ProjectStatus(str, Enum):
    """Project lifecycle status."""
    PROPOSAL = "proposal"
    LIVE = "live"
    FINISHED = "finished"
```

Update `ProjectDB.status` default:
```python
status: Mapped[str] = mapped_column(String(20), default="proposal", nullable=False)
```

Update `ProjectBase.status` default:
```python
status: ProjectStatus = ProjectStatus.PROPOSAL
```

- [ ] **Step 2: Update status filter whitelist**

In `backend/app/core/api/projects.py:57`, change:
```python
if filter_status and filter_status in ("proposal", "live", "finished"):
```

- [ ] **Step 3: Create Alembic migration**

Create `backend/alembic/versions/020_status_enum_migration.py`:
```python
"""Migrate project status: in_progress -> live, add proposal state.

Revision ID: 020_status_migration
Revises: 019_tracker_module
Create Date: 2026-03-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "020_status_migration"
down_revision: Union[str, None] = "019_tracker_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("UPDATE projects SET status = 'live' WHERE status = 'in_progress'")

def downgrade() -> None:
    op.execute("UPDATE projects SET status = 'in_progress' WHERE status = 'live'")
    op.execute("UPDATE projects SET status = 'in_progress' WHERE status = 'proposal'")
```

- [ ] **Step 4: Run migration and verify**

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard" python -m alembic upgrade head
psql scorecard -c "SELECT status, count(*) FROM projects GROUP BY status"
```

Expected: no `in_progress` rows, all converted to `live`.

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/ -x -q
```

Fix any test that hardcodes `in_progress` — change to `live` or `proposal`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/models/project.py backend/app/core/api/projects.py backend/alembic/versions/020_status_enum_migration.py
git commit -m "feat: migrate project status enum (in_progress→live, add proposal)"
```

---

## Task 2: Backend — ProjectResponse with program_name + code required

**Files:**
- Modify: `backend/app/core/models/project.py`

- [ ] **Step 1: Make code required on create**

In `ProjectCreate`, change code field:
```python
code: str = Field(..., min_length=1, max_length=100)
```

Keep `ProjectUpdate.code` as optional (`str | None`).

- [ ] **Step 2: Add ProjectResponse schema**

Add to `backend/app/core/models/project.py`:
```python
class ProjectResponse(Project):
    """Project response with resolved program name."""
    program_name: str | None = None
```

- [ ] **Step 3: Update exports**

In `backend/app/core/models/__init__.py`, add `ProjectResponse` to imports and `__all__`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/models/
git commit -m "feat: add ProjectResponse with program_name, require code on create"
```

---

## Task 3: Backend — New `/api/projects` Router

**Files:**
- Create: `backend/app/core/api/projects_v2.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create projects_v2 router**

Create `backend/app/core/api/projects_v2.py` with all CRUD endpoints. Key differences from existing `projects.py`:
- Uses `AdminUser` for POST/PUT/DELETE
- `list` searches by name AND code
- `list` returns `ProjectResponse` with `program_name` (LEFT JOIN to programs)
- `create` persists ALL fields (code, program_id, is_billable, currency, notes, summary, status)
- `replace` (PUT) persists ALL fields
- `delete` checks for report_parts/progress_reports before deleting

```python
"""Project CRUD endpoints (v2 — /api/projects)."""

import math
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from app.core.api.deps import AdminUser, CurrentUser, DBSession, get_project_or_404, limiter
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectCreate, ProjectDB, ProjectResponse, ProjectUpdate
from app.modules.scorecard.api.schemas.project import PaginatedProjectsResponse
from app.modules.scorecard.models.metrics.db import MetricsDB

router = APIRouter()

ALLOWED_SORT_FIELDS = {"name", "created_at", "status"}
MAX_PAGE_SIZE = 100


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _project_to_response(project: ProjectDB, program_name: str | None = None) -> ProjectResponse:
    data = {c.key: getattr(project, c.key) for c in project.__table__.columns}
    data["program_name"] = program_name
    return ProjectResponse.model_validate(data)


@router.get("")
@limiter.limit("100/minute")
async def list_projects(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    lightweight: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 45,
    search: str | None = None,
    filter_status: Annotated[str | None, Query(alias="status")] = None,
    sort: str | None = None,
    order: str | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
):
    if lightweight:
        result = await db.execute(select(ProjectDB).order_by(ProjectDB.name))
        projects = result.scalars().all()
        from app.modules.scorecard.api.schemas.project import ProjectSummary
        return [ProjectSummary.model_validate(p) for p in projects]

    program = aliased(ProgramDB)
    query = (
        select(ProjectDB, program.name.label("program_name"))
        .outerjoin(program, ProjectDB.program_id == program.id)
    )
    count_query = select(func.count()).select_from(ProjectDB)

    filters = []
    if search:
        safe = _escape_like(search)
        filters.append(
            (ProjectDB.name.ilike(f"%{safe}%")) | (ProjectDB.code.ilike(f"%{safe}%"))
        )
    if filter_status and filter_status in ("proposal", "live", "finished"):
        filters.append(ProjectDB.status == filter_status)
    if start_date_from:
        filters.append(ProjectDB.start_date >= start_date_from)
    if start_date_to:
        filters.append(ProjectDB.start_date <= start_date_to)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    sort_field = sort if sort in ALLOWED_SORT_FIELDS else "created_at"
    sort_order = order if order in ("asc", "desc") else "desc"
    sort_column = getattr(ProjectDB, sort_field)
    query = query.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()
    items = [_project_to_response(row[0], row[1]) for row in rows]

    return PaginatedProjectsResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_project(
    request: Request, project: ProjectCreate, admin: AdminUser, db: DBSession
) -> ProjectResponse:
    db_project = ProjectDB(
        name=project.name,
        code=project.code,
        program_id=project.program_id,
        is_billable=project.is_billable,
        currency=project.currency,
        notes=project.notes,
        summary=project.summary,
        jira_project_key=project.jira_project_key.upper() if project.jira_project_key else None,
        github_repo=project.github_repo,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status.value if project.status else "proposal",
        slack_channel_id=project.slack_channel_id,
    )
    db.add(db_project)
    await db.flush()
    await db.refresh(db_project)
    return _project_to_response(db_project)


@router.get("/{project_id}")
@limiter.limit("100/minute")
async def get_project(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> ProjectResponse:
    program = aliased(ProgramDB)
    result = await db.execute(
        select(ProjectDB, program.name.label("program_name"))
        .outerjoin(program, ProjectDB.program_id == program.id)
        .where(ProjectDB.id == project_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(row[0], row[1])


@router.put("/{project_id}")
@limiter.limit("30/minute")
async def replace_project(
    request: Request, project_id: UUID, data: ProjectCreate, admin: AdminUser, db: DBSession
) -> ProjectResponse:
    project = await get_project_or_404(db, project_id)
    project.name = data.name
    project.code = data.code
    project.program_id = data.program_id
    project.is_billable = data.is_billable
    project.currency = data.currency
    project.notes = data.notes
    project.summary = data.summary
    project.jira_project_key = data.jira_project_key.upper() if data.jira_project_key else None
    project.github_repo = data.github_repo
    project.start_date = data.start_date
    project.end_date = data.end_date
    project.status = data.status.value if data.status else project.status
    project.slack_channel_id = data.slack_channel_id
    await db.flush()
    await db.refresh(project)
    return _project_to_response(project)


@router.patch("/{project_id}")
@limiter.limit("30/minute")
async def update_project(
    request: Request, project_id: UUID, update: ProjectUpdate, admin: AdminUser, db: DBSession
) -> ProjectResponse:
    project = await get_project_or_404(db, project_id)
    update_data = update.model_dump(exclude_unset=True)
    if update_data.pop("clear_finished_at", False):
        project.finished_at = None
    for field, value in update_data.items():
        if field == "jira_project_key" and value:
            value = value.upper()
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return _project_to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_project(
    request: Request, project_id: UUID, admin: AdminUser, db: DBSession
) -> None:
    project = await get_project_or_404(db, project_id)

    # Check for tracker data that blocks deletion
    from app.modules.tracker.models.report_part import ReportPartDB
    from app.modules.tracker.models.progress_report import ProgressReportDB

    rp_count = (await db.execute(
        select(func.count()).select_from(ReportPartDB).where(ReportPartDB.project_id == project_id)
    )).scalar() or 0
    if rp_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete project with {rp_count} time report entries. Remove them first.",
        )

    pr_count = (await db.execute(
        select(func.count()).select_from(ProgressReportDB).where(ProgressReportDB.project_id == project_id)
    )).scalar() or 0
    if pr_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete project with {pr_count} progress reports. Remove them first.",
        )

    await db.execute(delete(MetricsDB).where(MetricsDB.project_id == project_id))
    await db.delete(project)
```

- [ ] **Step 2: Create programs router**

Create `backend/app/core/api/programs.py`:
```python
"""Programs list endpoint."""

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.models.program import Program, ProgramDB

router = APIRouter()


@router.get("")
@limiter.limit("100/minute")
async def list_programs(
    request: Request, current_user: CurrentUser, db: DBSession
) -> list[Program]:
    result = await db.execute(select(ProgramDB).order_by(ProgramDB.name))
    return [Program.model_validate(p) for p in result.scalars().all()]
```

- [ ] **Step 3: Mount in main.py**

In `backend/app/main.py`, add:
```python
from app.core.api import projects_v2 as projects_v2_router
from app.core.api import programs as programs_router

app.include_router(projects_v2_router.router, prefix="/api/projects", tags=["projects"])
app.include_router(programs_router.router, prefix="/api/programs", tags=["programs"])
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/ -x -q
```

- [ ] **Step 5: Manual API test**

```bash
curl -s http://localhost:8000/api/projects?page_size=3 | python -m json.tool | head -20
curl -s http://localhost:8000/api/programs | python -m json.tool
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/api/projects_v2.py backend/app/core/api/programs.py backend/app/main.py
git commit -m "feat: add /api/projects and /api/programs endpoints"
```

---

## Task 4: Frontend — Update Types and Services

**Files:**
- Modify: `frontend/src/core/types/project.ts`
- Modify: `frontend/src/core/services/projects.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`
- Create: `frontend/src/core/services/programs.ts`
- Create: `frontend/src/core/hooks/usePrograms.ts`

- [ ] **Step 1: Update project types**

In `frontend/src/core/types/project.ts`:
```typescript
import type { PaginatedResponse } from './common';

export type ProjectStatus = 'proposal' | 'live' | 'finished';

export interface Project {
  id: string;
  name: string;
  code: string | null;
  program_id: string | null;
  program_name: string | null;
  is_billable: boolean;
  currency: string | null;
  notes: string | null;
  summary: string | null;
  jira_project_key: string | null;
  github_repo: string | null;
  slack_channel_id: string | null;
  start_date: string | null;
  end_date: string | null;
  status: ProjectStatus;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  code: string;
  program_id?: string | null;
  is_billable?: boolean;
  currency?: string | null;
  notes?: string | null;
  summary?: string | null;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
}

export interface ProjectUpdate {
  name?: string;
  code?: string;
  program_id?: string | null;
  is_billable?: boolean;
  currency?: string | null;
  notes?: string | null;
  summary?: string | null;
  jira_project_key?: string;
  github_repo?: string;
  slack_channel_id?: string | null;
  start_date?: string;
  end_date?: string;
  status?: ProjectStatus;
  finished_at?: string;
  clear_finished_at?: boolean;
}

export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
}

export type PaginatedProjects = PaginatedResponse<Project>;

export interface ProjectSummary {
  id: string;
  name: string;
}

export interface ProjectListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  sort?: string;
  order?: string;
  start_date_from?: string;
  start_date_to?: string;
}

export interface ProgramSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Add projects v2 API service**

In `frontend/src/core/services/projects.ts`, add new methods pointing to `/projects`:
```typescript
export const projectsCoreApi = {
  list: async (params: ProjectListParams = {}): Promise<PaginatedProjects> => {
    const response = await api.get<PaginatedProjects>('/projects', { params });
    return response.data;
  },

  get: async (id: string): Promise<Project> => {
    const response = await api.get<Project>(`/projects/${id}`);
    return response.data;
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await api.post<Project>('/projects', data);
    return response.data;
  },

  replace: async (id: string, data: ProjectCreate): Promise<Project> => {
    const response = await api.put<Project>(`/projects/${id}`, data);
    return response.data;
  },

  update: async (id: string, data: ProjectUpdate): Promise<Project> => {
    const response = await api.patch<Project>(`/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`);
  },
};
```

Keep the existing `projectsApi` (points to `/scorecards`) for backward compatibility.

- [ ] **Step 3: Create programs service**

Create `frontend/src/core/services/programs.ts`:
```typescript
import type { ProgramSummary } from '@/types';
import api from './client';

export const programsApi = {
  list: async (): Promise<ProgramSummary[]> => {
    const response = await api.get<ProgramSummary[]>('/programs');
    return response.data;
  },
};
```

- [ ] **Step 4: Add query keys**

In `frontend/src/core/hooks/queryKeys.ts`, add:
```typescript
programs: {
  all: ['programs'] as const,
  list: ['programs', 'list'] as const,
},
```

- [ ] **Step 5: Create programs hook**

Create `frontend/src/core/hooks/usePrograms.ts`:
```typescript
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { programsApi } from '@/core/services/programs';

export const usePrograms = () =>
  useQuery({
    queryKey: queryKeys.programs.list,
    queryFn: programsApi.list,
    staleTime: 5 * 60 * 1000,
  });
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/types/ frontend/src/core/services/ frontend/src/core/hooks/
git commit -m "feat: update project types, add /projects API service and programs hook"
```

---

## Task 5: Frontend — Sidebar + Routes

**Files:**
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add Projects to sidebar**

In `AppSidebar.tsx`, add a "Projects" item before "Scorecard" in the navigation group:
```tsx
{ title: 'Projects', url: '/projects', icon: FolderKanban }
```

Import `FolderKanban` from `lucide-react`.

- [ ] **Step 2: Add routes**

In `App.tsx`, add inside the protected layout routes:
```tsx
<Route path="/projects" element={<ProjectsIndex />} />
<Route path="/projects/new" element={<AdminRoute><ProjectFormPage /></AdminRoute>} />
<Route path="/projects/:id/edit" element={<AdminRoute><ProjectFormPage /></AdminRoute>} />
```

Change default redirect from `/scorecard` to `/projects`.

Create placeholder components for now (will implement in next tasks).

- [ ] **Step 3: Verify sidebar and routes work**

Navigate to http://localhost:5173 — should redirect to `/projects`. Sidebar should show "Projects" as first item.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/components/layout/AppSidebar.tsx frontend/src/App.tsx
git commit -m "feat: add Projects to sidebar and routes"
```

---

## Task 6: Frontend — Projects Index Page

**Files:**
- Create: `frontend/src/core/hooks/useProjectListParams.ts`
- Create: `frontend/src/core/components/ProjectCard.tsx`
- Create: `frontend/src/core/pages/Projects.tsx`

- [ ] **Step 1: Create useProjectListParams hook**

In `frontend/src/core/hooks/useProjectListParams.ts`. Same pattern as `modules/scorecard/hooks/useProjectListParams.ts` but with updated status values (`proposal`, `live`, `finished`).

- [ ] **Step 2: Create ProjectCard component**

In `frontend/src/core/components/ProjectCard.tsx`. Displays: name, status badge (Proposal=yellow, Live=blue, Finished=green), code, is_billable, program_name, jira, github, dates, score, burn %. Action links: Scorecard, Edit (admin only).

Follow the pattern from `modules/scorecard/components/Dashboard/ProjectCard.tsx` but adapted for the new fields.

- [ ] **Step 3: Create Projects index page**

In `frontend/src/core/pages/Projects.tsx`. Same pattern as `modules/scorecard/pages/Projects.tsx`: search, status filters, date range, sort, pagination, list/grid views. Uses `projectsCoreApi.list()` and the new `useProjectListParams`.

Create button visible only to admins, navigates to `/projects/new`.

- [ ] **Step 4: Wire up React Query hooks**

Add to `frontend/src/core/hooks/useProjects.ts`:
```typescript
export const usePaginatedCoreProjects = (params: ProjectListParams) =>
  useQuery({
    queryKey: queryKeys.projects.list(params),
    queryFn: () => projectsCoreApi.list(params),
    keepPreviousData: true,
  });
```

- [ ] **Step 5: Verify**

Navigate to http://localhost:5173/projects — should show the full project list with filters and cards.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/
git commit -m "feat: Projects index page with filters, sort, and project cards"
```

---

## Task 7: Frontend — Project Form (Create/Edit)

**Files:**
- Create: `frontend/src/core/pages/ProjectForm.tsx`

- [ ] **Step 1: Create ProjectForm page**

In `frontend/src/core/pages/ProjectForm.tsx`. Handles both create (`/projects/new`) and edit (`/projects/:id/edit`) modes. Uses `useParams()` to detect mode.

Fields: name*, code*, status (select), is_billable (switch), currency (select), program (select from `usePrograms()`), jira_project_key, github_repo, slack_channel (combobox), start_date, end_date, notes (textarea), summary (textarea).

Actions: Save/Create, Cancel, Delete (edit only, with AlertDialog confirmation), Mark as Finished / Reopen.

Non-admin sees 403 message (the route is already wrapped in `AdminRoute`, but add a fallback).

- [ ] **Step 2: Add mutations**

Add to `frontend/src/core/hooks/useProjects.ts`:
```typescript
export const useCreateCoreProject = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsCoreApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projects.all }),
  });
};

export const useReplaceCoreProject = (id: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsCoreApi.replace(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(id) });
    },
  });
};

export const useDeleteCoreProject = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => projectsCoreApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.projects.all }),
  });
};
```

- [ ] **Step 3: Verify create flow**

Navigate to `/projects/new`, fill form, submit. Project appears in list.

- [ ] **Step 4: Verify edit flow**

Click Edit on a project card. Form pre-populated. Change a field, save. Changes reflected.

- [ ] **Step 5: Verify delete flow**

In edit mode, click Delete, confirm in dialog. Project removed from list.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/
git commit -m "feat: Project create/edit form with all fields"
```

---

## Task 8: Update Scorecard Frontend for New Status Values

**Files:**
- Modify: `frontend/src/modules/scorecard/pages/Projects.tsx`
- Modify: `frontend/src/modules/scorecard/components/Dashboard/ProjectCard.tsx`
- Modify: `frontend/src/modules/scorecard/hooks/useProjectListParams.ts`

- [ ] **Step 1: Update status filter buttons**

In scorecard's `Projects.tsx`, change status filter options from `in_progress`/`finished` to `proposal`/`live`/`finished`.

- [ ] **Step 2: Update status badge in ProjectCard**

Change badge labels and colors: Proposal=yellow, Live=blue, Finished=green.

- [ ] **Step 3: Update useProjectListParams defaults**

Change default status handling to use new values.

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Fix any tests that reference `in_progress`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/scorecard/
git commit -m "feat: update scorecard UI for new project status values"
```

---

## Task 9: Final Verification and Push

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -x -q
```

- [ ] **Step 2: Run all frontend tests**

```bash
cd frontend && npm test -- --run
```

- [ ] **Step 3: Manual E2E verification**

1. `/projects` — list loads with all projects, filters work, search by name and code works
2. `/projects/new` — create with required fields (name, code), verify in list
3. `/projects/:id/edit` — edit all fields, save, verify changes
4. `/projects/:id/edit` — delete project (one without tracker data), confirm removal
5. `/scorecard` — status badges show new values (Proposal/Live/Finished)
6. Non-admin user — cannot access create/edit (403)
7. Sidebar — Projects link active, redirects from `/` work

- [ ] **Step 4: Push**

```bash
git push
```
