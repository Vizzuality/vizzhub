# XLSX Export Service Design

## Overview

A reusable export service that generates XLSX files with project scorecard data. Designed to be extensible for future modules (e.g., VizzTracker). Two initial export types: project detail and global dashboard, both with monthly breakdown and ISO audit-ready formatting.

## Export Types

### 1. Project Detail Export

Single project, scores and metrics broken down by month.

**Endpoint:** `GET /api/exports/project/{id}?start=2025-01&end=2025-12&snapshot_type=cumulative`

**Filename:** `{project_name}_scorecard_{start}_{end}.xlsx`

**Sheets:**

#### Sheet 1: Summary

Project metadata:
- Name, status, team
- Start date, end date, finished_at
- Jira key, GitHub repo
- Export date and snapshot type

Final score per month in a row with month columns.

#### Sheet 2: Metrics (main audit sheet)

Hierarchical rows with 4 fixed columns + month value columns:

```
| Name (bold)        | Description           | Formula              | Target | Jan 2025 | Feb 2025 | ...
|--------------------|----------------------|----------------------|--------|----------|----------|
| FINAL SCORE        | Overall project...   | Weighted average...  |        |    78    |    82    |
|   P_time           | Schedule perf...     | w1*SPI + w2*...      | 0.80   |    85    |    88    |
|     SPI            | Schedule Perf...     | EV / PV              | 0.80   |   0.92   |   0.95   |
|   P_quality        | Software quality...  | w1*defect + w2*...   | 0.80   |    72    |    75    |
|     defect_density | Defects per...       | bugs / kloc          |        |   0.03   |   0.02   |
|     test_maturity  | Testing process...   | 1-5 scale            |        |    3     |    3     |
| ...                |                      |                      |        |          |          |
```

Formatting:
- Name column: bold, indented by hierarchy level (score > dimension > sub-indicator)
- Value cells: traffic light colors (green >= target, yellow within 20% of target, red < 80% of target)
- First 4 columns frozen (freeze panes)
- Month headers in first row
- Column widths auto-adjusted

#### Sheet 3: Methodology

Additional context for auditors:
- Global dimension weights and how final score is computed
- Explanation of the scoring model (raw -> normalized -> weighted -> score)
- Traffic light legend (green/yellow/red thresholds)
- Snapshot type explanation (cumulative vs punctual)
- Current configuration timestamp

### 2. Global Dashboard Export

All projects compared, scores by month.

**Endpoint:** `GET /api/exports/global?start=2025-01&end=2025-12&snapshot_type=cumulative`

**Filename:** `global_scorecard_{start}_{end}.xlsx`

**Sheets:**

#### Sheet 1: Overview

Projects as rows, months as columns, final score values with traffic light colors.

```
| Project Name    | Jan 2025 | Feb 2025 | Mar 2025 | ...
|-----------------|----------|----------|----------|
| Project Alpha   |    78    |    82    |    75    |
| Project Beta    |    91    |    88    |    90    |
```

#### Sheet 2: Dimensions

One block per dimension (P_time, P_quality, etc.), separated by empty rows. Each block has:
- Header row with dimension name
- Projects as rows, months as columns, dimension scores with traffic light colors

#### Sheet 3: Methodology

Same shared methodology sheet as project detail export.

## Architecture

### Backend

```
backend/app/
  services/
    export_service.py      # ExportService class
    export_helpers.py      # Shared: methodology sheet, styling, traffic light
  api/
    exports.py             # Router: 2 GET endpoints
```

**ExportService:**
- `export_project_detail(project_id, start_year, start_month, end_year, end_month, snapshot_type) -> BytesIO`
- `export_global_dashboard(start_year, start_month, end_year, end_month, snapshot_type) -> BytesIO`

Both return an in-memory XLSX file (BytesIO). No disk writes.

**export_helpers.py** shared functions:
- `create_methodology_sheet(wb, config)` — generates the methodology sheet from current ScoringConfig
- `apply_header_style(ws, row)` — bold, background color, freeze panes
- `apply_traffic_light(cell, value, target)` — green/yellow/red fill
- `set_column_widths(ws)` — auto-adjust column widths
- Metric definitions: name, description, formula per KPI (static content enriched with live config values)

**Endpoints** return `StreamingResponse`:
```python
return StreamingResponse(
    content=output.getvalue(),
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    headers={"Content-Disposition": f"attachment; filename={filename}"}
)
```

**Dependencies** (existing, no new models/tables):
- `ScoringConfig` — weights, targets, ideals
- Score calculators — compute scores per period
- Metrics DB queries — raw metrics by date range
- Projects DB queries — project metadata

**New dependency:**
- `openpyxl` — XLSX generation

### Frontend

**Project Detail** (`SnapshotManager.tsx`):
- Replace disabled CSV button with:
  - Two month-year pickers (from/to)
  - Snapshot type selector (cumulative/punctual)
  - "Export XLSX" button
- Download via fetch + blob + `<a download>`

**Global Dashboard** (`GlobalDashboard/index.tsx`):
- Add export card/button with same controls:
  - Two month-year pickers (from/to)
  - Snapshot type selector (cumulative/punctual)
  - "Export XLSX" button

**No new frontend dependencies.** Download is a direct file fetch:
```typescript
const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
const blob = await response.blob();
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = filename;
a.click();
```

## Extensibility

The service is designed for future modules:
- `export_helpers.py` contains all shared formatting logic
- New export types (e.g., VizzTracker budget report) add a method to ExportService and an endpoint
- Methodology sheet generator accepts config parameters, adaptable per module
- Traffic light and styling functions are generic

## Data Flow

```
Frontend (button click)
  → GET /api/exports/project/{id}?start=...&end=...&snapshot_type=...
    → ExportService.export_project_detail()
      → Query metrics for date range
      → Compute scores per period (on-the-fly)
      → Load current ScoringConfig (weights, targets, ideals)
      → Build XLSX with openpyxl (summary + metrics + methodology)
      → Return BytesIO
    → StreamingResponse (XLSX download)
```
