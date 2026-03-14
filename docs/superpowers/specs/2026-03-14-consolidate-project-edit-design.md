# Consolidate Project Edit - Design Spec

**Goal:** Eliminate the duplicate scorecard ProjectForm and move EVM/Milestones editing into the core ProjectForm, creating a single edit experience at `/projects/:id/edit`.

**Architecture:** The core ProjectForm becomes the sole place to edit project data, including Budget & Schedule (EVM) and Milestones. The scorecard detail becomes read-only for these sections, with an "Edit" link navigating to the core form. A new backend endpoint handles EVM+Milestones upsert without requiring pre-existing metrics.

---

## 1. Frontend - Expanded ProjectForm

### Location
`frontend/src/core/pages/ProjectForm.tsx`

### New Sections (always visible, not collapsible)

After the existing Notes/Summary fields, add:

**Budget & Schedule section:**
- Fields: Budget Total, Actual Cost, Work Completed %, Expected Progress %
- All fields optional (budget can exist without cost/progress)
- Real-time calculated preview of EV, SPI, CPI (extract calculation helpers to `shared/` utility)
- Empty fields are not sent to the API

**Milestones section:**
- Dynamic array: Name (required if row has data), Planned Date (required if row has data), Actual Date (optional)
- "Add Milestone" button
- Delete button per row
- Starts with one empty row; empty rows are stripped before submit

### Unified Save

Single "Save Changes" / "Create Project" button:

**Edit mode (`/projects/:id/edit`):**
1. `PUT /projects/:id` for project fields
2. `PUT /projects/:id/budget` for EVM + Milestones (if any data present)
3. Both calls in parallel

**Create mode (`/projects/new`):**
1. `POST /projects` - returns new project with `id`
2. If EVM or milestones data present: `PUT /projects/:id/budget` using returned `id`
3. Sequential (needs id from step 1)

### Data Loading (edit mode)

On mount, fetch both:
- Project data: existing `useProject(id)` hook
- Current period metrics: existing `useProjectMetrics(id, currentYear, currentMonth)` hook - populates EVM + milestones fields

Current period = system date's year/month (not related to scorecard's period selector).

### Form State

EVM and milestones fields are managed within the same `react-hook-form` instance as project fields. No separate form state.

### EVM Field Validation

All EVM fields are **optional** (no required validation). This differs from the current EVMForm which requires all four fields. The new behavior:
- `budget_total` alone is valid (use case: project setup before work starts)
- `cost_to_date`, `percent_completed`, `percent_planned` can be filled independently
- SPI/CPI preview only shows when the required inputs for each formula are present

### Error Handling (create mode)

If `POST /projects` succeeds but `PUT /projects/:id/budget` fails:
- Project is created (user sees success navigation)
- EVM/milestones data is lost from the form but can be re-entered by editing the project
- No rollback - this is acceptable since budget data is supplementary

---

## 2. Backend - New Budget Endpoint

### Endpoint
`PUT /projects/{project_id}/budget`

### Location
`backend/app/core/api/projects_v2.py` (alongside existing project endpoints)

### Request Schema
```python
class ProjectBudgetUpdate(BaseModel):
    evm_data: EVMData | None = None
    milestones: list[Milestone] | None = None
```

### Behavior
1. Determine current period (year, month)
2. Find or create metrics record for this project + period (upsert)
3. If `evm_data` provided: update EVM fields (only non-None subfields)
4. If `milestones` provided: replace milestones array
5. Recalculate scores after update
6. Invalidate score cache

### Auth
`AdminUser` (same as project write endpoints)

### Why a new endpoint instead of reusing existing metrics endpoints
- Existing `PUT /metrics/{metricsId}/evm` requires a metrics ID, which doesn't exist for new projects or projects that haven't captured yet
- The new endpoint uses project_id and auto-creates metrics, simplifying the frontend flow
- Existing endpoints remain for the capture system and other internal callers

---

## 3. Remove Scorecard ProjectForm

### Delete
- `frontend/src/modules/scorecard/components/Forms/ProjectForm.tsx`

### Modify `ProjectHeader.tsx`
- Remove `isEditing` state and conditional form render
- Remove props: `onEdit`, `onCancelEdit`, `onSubmitEdit`, `isSubmitting`
- Keep props: `onMarkFinished`, `onReopen`, `onDelete`, `isUpdatingStatus` (status controls stay in scorecard header)
- "Edit" button in `StatusControls` becomes `<Link to={/projects/${project.id}/edit}>`

### Status Controls Ownership
Both core ProjectForm and scorecard ProjectHeader have status controls (Mark Finished / Reopen). This is intentional - users can change status from either place. Core ProjectForm already has these buttons (lines 267-290). No changes needed to status control logic.

### Modify `ProjectDetail.tsx`
- Remove `isEditing` state
- Remove `replaceProject` mutation
- Remove `handleEdit` function
- Simplify `ProjectHeader` props

---

## 4. Scorecard EVMSection - Read Only

### Modify `EVMSection.tsx`
- Remove "Edit" / "Add EVM Data" button
- Remove all editing state (`isEditingEVM`, `isEditingMilestones`, `hasMilestoneChanges`, etc.)
- Remove `EVMForm` and `MilestonesForm` imports
- Remove discard alert dialog
- Remove `onUpdateEVM`, `onUpdateMilestones`, `isUpdatingEVM`, `isUpdatingMilestones` props
- Keep read-only display: `EVMDataGrid`, milestone list, SubIndicatorCards with historical charts
- If no EVM data: show message with `<Link to={/projects/${projectId}/edit}>Edit project</Link>` to add it

### Modify `ProjectDetail.tsx`
- Remove `useUpdateEVMData`, `useUpdateMilestones` hooks
- Remove `handleUpdateEVM`, `handleUpdateMilestones` functions
- Simplify `EVMSection` props (remove all mutation-related props)

---

## 5. What Does NOT Change

- Other metric cards (Governance, PM Satisfaction, Client Survey, Architecture, Test Maturity, Strategic Impact) remain inline-editable in scorecard detail
- Existing `PUT /metrics/{id}/evm` and `PUT /metrics/{id}/milestones` endpoints remain (used by capture system)
- SubIndicatorCards with historical charts stay in scorecard detail only (not in ProjectForm)
- The form's calculated values preview is the simple card (EV, SPI, CPI) without historical data

---

## 6. Edge Cases

- **No metrics record exists (new project or never captured):** The `PUT /projects/:id/budget` endpoint creates it automatically for the current period
- **Empty EVM fields:** If all EVM fields empty, don't send `evm_data` at all. Partial: budget_total alone is valid (cost/progress can be empty)
- **Empty milestones:** Rows with no name+planned_date are stripped before submit. If all rows empty, omit `milestones` from request
- **Cost field will become automatic:** When VizzTracker is active, `cost_to_date` will be computed. For now it's manual. No special handling needed - the field will simply become read-only in a future iteration
- **Period:** Always current period. No period selector in ProjectForm
