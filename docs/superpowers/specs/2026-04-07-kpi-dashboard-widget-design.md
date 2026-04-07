# KPI Dashboard Widget — Design Spec

## Summary

A widget for the ISO Docs tree that combines live Global Scorecard data with manually-entered ISO KPIs in a single, exportable view. The widget serves as the ISO audit-ready KPI registry, replacing the legacy "Indicadores" Excel spreadsheet.

## Context

ISO 27001 audits (annually, late March / early April) require a documented KPI registry with methodology, targets, and monthly values. Currently this is maintained as a separate Excel file with ~30 indicators — most unrealistic and always zero.

The Hub already computes Global Scorecard metrics (8 dimensions, 20+ indicators) automatically from project data. This widget surfaces those metrics alongside a small set of manually-tracked ISO-specific KPIs that aren't covered by the scorecard (e.g., security training completion).

## Approach

**Widget puro** (Approach 1 from brainstorming):

- Scorecard data rendered live from existing APIs — always current, zero maintenance
- Manual KPIs stored as standard `RegistryRow` entries — reuses existing CRUD infrastructure
- Dedicated export endpoint merges both sections into XLSX / Google Drive

No new DB models, no migrations, no seed scripts.

## ISO Cycle

The ISO cycle runs **March to February** (e.g., cycle "2025-2026" = March 2025 → February 2026). The audit happens late March / early April.

The widget's year selector maps to this cycle: selecting "2025" means months `m03` (Mar 2025) through `m02` (Feb 2026). This matches how all other yearly registries in ISO Docs already work.

## Data Sources

### Scorecard Section (live, read-only)

Consumed APIs (already exist, no changes needed):

- `GET /api/scorecard/global/history?limit=12` — monthly indicator + score values
- `GET /api/scorecard/config` — targets, global weights, dimension weights

The hierarchical structure (Final Score → 8 dimensions → 20+ indicators) is defined as a TypeScript constant mirroring `backend/app/modules/scorecard/services/export_definitions.py`, which already contains:

- `DIMENSION_DEFINITIONS`: key, name, description, formula, indicators[]
- `INDICATOR_DEFINITIONS`: name, description, formula per indicator

For a given ISO cycle (e.g., 2025), the widget filters history records to months March 2025 through February 2026.

### Manual KPIs Section (editable)

Uses existing `RegistryRow` model — no new tables. The widget node (`node_id`) owns the rows. Each row's `year` field = ISO cycle year (e.g., 2025). The `data` JSONB stores:

```json
{
  "name": "% empleados con formación de seguridad",
  "scope": "Concienciación",
  "responsible": "RRHH",
  "methodology": "Porcentaje de empleados que han completado la capacitación anual",
  "formula": "empleados_formados / total_empleados",
  "target": 0.8,
  "periodicity": "Anual",
  "m03": null,
  "m04": null,
  "m05": null,
  "m06": null,
  "m07": null,
  "m08": null,
  "m09": null,
  "m10": null,
  "m11": null,
  "m12": null,
  "m01": null,
  "m02": null
}
```

Existing endpoints handle CRUD:

- `GET /api/iso-docs/registries/{node_id}/rows?year=2025`
- `POST /api/iso-docs/registries/{node_id}/rows`
- `PATCH /api/iso-docs/registries/{node_id}/rows/{row_id}`
- `DELETE /api/iso-docs/registries/{node_id}/rows/{row_id}`

Editors can add new KPIs at any time with full methodology fields — this is mandatory for ISO.

## Widget UI

### Layout

```
┌─────────────────────────────────────────────────────┐
│ [Toolbar]  Ciclo: [◄ 2025-2026 ►]  [Export XLSX ▼] │
├─────────────────────────────────────────────────────┤
│ GLOBAL SCORECARD                                     │
│ ┌───────────────────────────────────────────────────┐│
│ │ Name          │ Formula │ Target │ Weight │ Mar…  ││
│ │───────────────│─────────│────────│────────│───────││
│ │ FINAL SCORE   │ Sum(…)  │   80   │        │ 68.5 ││
│ │ ▼ P_time      │ w_spi…  │   80   │  12%   │ 78.9 ││
│ │   SPI         │ EV/PV   │  0.8   │  60%   │ 0.80 ││
│ │   Milestones  │ Sum(…)  │  1.0   │  40%   │ 0.70 ││
│ │ ► P_cost      │         │   80   │  10%   │ 78.7 ││
│ │ ► P_quality   │         │   80   │  20%   │ 73.5 ││
│ │ …                                                 ││
│ └───────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│ KPIs MANUALES                              [+ Add]  │
│ ┌───────────────────────────────────────────────────┐│
│ │ Name │ Scope │ Resp. │ Method │ Target │ Mar …  ││
│ │──────│───────│───────│────────│────────│────────││
│ │ % formación │ Conc. │ RRHH │ empl…  │  80%  │ … ││
│ └───────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Scorecard Table Behavior

- **Hierarchical**: Final Score → dimensions (collapsible ▼/►) → indicators
- **Columns (fixed)**: Name, Description (truncated), Formula, Target, Weight
- **Columns (scrollable)**: Mar, Apr, May, ..., Jan, Feb (12 months of the ISO cycle)
- **Traffic light**: cell background color based on value vs target:
  - Scores (0-100): green ≥ 80, yellow ≥ 60, red < 60
  - Indicators (0-1): green ≥ 0.80, yellow ≥ 0.60, red < 0.60
- **Read-only**: no inline editing — data comes from the API
- **Project count**: shown as subtitle or in the Final Score row

### Manual KPIs Table Behavior

- **Columns (fixed)**: Name, Scope, Responsible, Methodology, Formula, Target, Periodicity
- **Columns (scrollable)**: Mar, Apr, ..., Jan, Feb (same 12 months)
- **Inline editing**: monthly value cells are editable (reuses `InlineCell` component)
- **Add KPI button**: opens dialog with fields: name, scope, responsible, methodology, formula, target, periodicity
- **Delete/edit**: row actions like existing registries
- **No traffic light on manual KPIs** (targets vary too much in type — counts, percentages, hours)

### Cycle Selector

`◄ 2025-2026 ►` navigation. Available cycles derived from global metrics available months + registry row years (union). Arrows navigate between cycles.

### Export Dropdown

- **"Excel"**: downloads XLSX via the new export endpoint
- **"Google Drive"**: uploads to Drive (if connected), same XLSX content

## Export Endpoint

```
GET /api/iso-docs/widgets/{node_id}/export?year=2025&format=xlsx
```

Location: `backend/app/modules/iso_docs/api/widget_export.py`

Mounted on the ISO Docs router under `prefix="/widgets"`.

Requires: `IsoDocsViewer` (read-only operation).

### XLSX Structure

**Sheet 1: "Global Scorecard"**

- Header row: "Global Dashboard — Ciclo 2025-2026"
- Row: "Projects: N" (from project_count)
- Column headers: Name, Description, Formula, Target, Weight, Mar 2025, Apr 2025, ..., Feb 2026
- Hierarchical rows:
  - Level 0: FINAL SCORE (bold)
  - Level 1: Dimensions (bold, indented 2 spaces)
  - Level 2: Indicators (indented 4 spaces)
- Conditional formatting: green/yellow/red fill on monthly value cells
- Data from: `GlobalMetricsService.get_history()` + `ScoringConfig` + `export_definitions.py`

**Sheet 2: "KPIs manuales"**

- Column headers: Name, Scope, Responsible, Methodology, Formula, Target, Periodicity, Mar 2025, ..., Feb 2026
- One row per manual KPI
- Data from: `RegistryRow` entries for the node + year

### Drive Export

Reuses the XLSX generation, uploads as Google Sheets spreadsheet to the node's mapped Drive folder. Integrates with the existing `drive_export_service.py` flow.

## File Structure

### Frontend

```
frontend/src/modules/iso-docs/components/widgets/
  index.ts                    — WIDGET_REGISTRY (updated to include kpi_dashboard)
  KpiDashboard/
    index.tsx                 — re-export
    KpiDashboard.tsx          — main layout: toolbar + 2 sections
    ScorecardTable.tsx        — hierarchical live table (read-only)
    ManualKpiTable.tsx        — editable table (uses InlineCell)
    AddKpiDialog.tsx          — dialog for new manual KPI
    constants.ts              — DIMENSION_DEFINITIONS, INDICATOR_DEFINITIONS
    types.ts                  — local interfaces (ScorecardRow, ManualKpiRow, IsoCycle)
    useKpiDashboard.ts        — hook: combines global metrics + config + registry rows
```

### Backend

```
backend/app/modules/iso_docs/api/
  widget_export.py            — GET /widgets/{node_id}/export endpoint
```

The widget export router is included in the ISO Docs module router.

## What This Does NOT Include

- No new DB models or migrations
- No seed scripts — editor creates the widget node and manual KPIs via UI
- No changes to the global metrics API or scoring engine
- No changes to the existing registry system (RegistryRow, RegistryView, etc.)
- No changes to the node model (widget type + widget_key already supported)

## Testing

### Backend

- `test_widget_export.py`: export endpoint returns valid XLSX with 2 sheets, correct month columns for ISO cycle, hierarchical scorecard rows, manual KPI rows

### Frontend

- `KpiDashboard.test.tsx`: renders both sections, scorecard table shows dimensions/indicators from mock global metrics, manual KPI table shows rows from mock registry data
- `ScorecardTable.test.tsx`: collapse/expand dimensions, traffic light colors, correct month filtering for ISO cycle
- `ManualKpiTable.test.tsx`: add/edit/delete KPI, inline editing of monthly values
