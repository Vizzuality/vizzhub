# Accrual lines — design doc (epic)

> **Status:** DRAFT for CTO review · 2026-05-29 · author: pairing session
> **Decision captured in:** memory `accrual-lines-model`, `accrual-drift-triage`.
> **Do not start coding until this is signed off.** Public repo — no client codes here
> (those live in the gitignored `docs/superpowers/accrual_unmatched_triage_2026-05-29.md`).

## 1. Why

The accrual module recognises revenue per month against the CEO's forecast Excel.
The current model keys every cell to a **project** (`project_accrual_cells.project_id`,
unique on `(project_id, year, month)`) and the importer infers the project↔Excel
mapping through a stack of heuristics. That model has five structural problems,
all surfaced empirically during the 2026-05-29 seed + unmatched triage:

1. **Overlapping contracts on the same project collide.** One project can carry
   several revenue lines over time (e.g. a maintenance project that absorbs an
   FY24 extension *and* an FY25 extension). With `(project_id, year, month)` unique,
   two lines competing for the same month overwrite each other.
2. **`cell_in_range` gating silently drops cells.** `importer/cells.py` only writes
   Excel cells whose `(year, month)` is inside the tracker contract `[start_date,
   end_date]`. The seed dropped **147 cells across 67 projects** this way — real
   CEO-forecast revenue, gone, because the accrual horizon legitimately runs past
   the contracted end (projects slip; revenue is recognised later).
3. **The accrual window is welded to the contract.** There is no place to express
   "this project's revenue recognition runs Oct-24 → Sep-25" independently of the
   signed contract dates. The CEO needs that flexibility; the contract stays ground
   truth (we never mutate tracker dates to model a forecast — see drift doctrine).
4. **No unlinked revenue.** A cell *requires* a `project_id`. Real income with no
   tracker project (future grants, untracked revenue) cannot be represented at all,
   so it either gets force-fit to a wrong project or dropped.
5. **Multi-project imputation is lossy and ambiguous.** `apply_multi_project`
   imputes each Excel month to "the project whose range contains it", drops months
   no project covers (orphans), and refuses months >1 project covers (ambiguous).
   It also splits `original_budget` proportionally — a fabricated per-project number.

## 2. The model

The unit of revenue recognition becomes the **accrual line**, not the project.

```
accrual_lines               accrual_line_projects          accrual_cells
─────────────               ─────────────────────          ─────────────
id            (uuid pk)     line_id   (fk → lines)          id          (uuid pk)
name          (text)        project_id(fk → projects)       line_id     (fk → lines, CASCADE)
source        (excel|       (pk: line_id, project_id)       year        (int)
               team_budget|                                 month       (int)
               manual)      -- 0..N rows per line --        amount      (numeric 14,2, EUR)
excel_code    (text, null)                                  is_manual_override (bool)
import_run_id (fk, null)                                    is_frozen   (bool)
value_orig    (numeric,null)                                frozen_at   (ts, null)
currency      (char3, null)                                 frozen_eur_amount (numeric, null)
rate          (numeric, null)                               source      (excel|team_budget|manual)
value_eur     (numeric)                                     updated_at  (ts)
window_start  (date)                                        UNIQUE (line_id, year, month)
window_end    (date)
created_by    (fk users, null)
created_at / updated_at
```

### Cardinality

- **`accrual_lines ↔ projects` is `0..N : 0..N`** via `accrual_line_projects`.
  - A line touches **N** projects (one grant spanning sibling projects).
  - A project carries **N** lines (a maintenance project absorbing several
    extensions; overlapping windows are fine — they're separate lines).
  - A line touches **0** projects — an **unlinked line**: real income with no
    tracker project, ever (future grant, untracked revenue). It still counts
    toward the company accrual total and renders as a grid row with no project tag.
- **Cells hang off the line** (`accrual_cells.line_id`), *not* the project. This is
  the fix for problem #1 — two overlapping lines on one project keep distinct cell
  rows because the unique key is `(line_id, year, month)`.

### Window decoupled from contract

- `window_start` / `window_end` live **on the line** and are editable by an
  `ACCRUAL_MANAGE` user.
- Initial value at import = `union(contract dates of linked projects, Excel month
  span)`. So nothing is dropped (kills problem #2) and the default is sensible.
- For an **unlinked** line, the window initialises from the Excel span alone.
- The tracker contract (`projects.start_date/end_date`) is **never written** by
  accrual. The window is the CEO's forecast frame and legitimately diverges.

### No per-project € split

The line (grant/contract) is the reporting unit. We do **not** split a line's value
across its linked projects — per-project burn/cost already lives in tracker, and
revenue is recognised per contract. If a per-project rollup is ever needed, add a
`share` numeric to `accrual_line_projects` (deferred — probably never). This kills
the fabricated proportional `original_budget` split.

## 3. What this kills

| Removed | Replaced by |
|---|---|
| `cell_in_range` gating (`importer/cells.py`) | line window = `union(contract, excel)`, no drop |
| `apply_multi_project` imputation / orphans / ambiguous | one line linked to N projects; cells stay on the line |
| proportional `original_budget` split | `line.value_eur` is canonical; no split |
| `project_accrual_cells.project_id` keying | `accrual_cells.line_id` keying |
| team-budget fallback writing project cells | a `source='team_budget'` line per eligible project |
| grid health comparing Σcells(EUR) vs `project.budget` (orig currency → FX noise) | Σline-cells(EUR) vs `line.value_eur` (same provenance — **no FX contamination**) |

> Note on currency: comparing line cells to `line.value_eur` removes the ~7-8% FX
> contamination from the health badge **for free**, because both are EUR from the
> same Excel row. The broader site-wide FX model (budgets in original currency,
> per-period CEO rate) stays a separate, later epic — see memory
> `accrual-period-fx-rates`. We do **not** patch currency here beyond what the
> line-keying naturally fixes.

## 4. The importer is retired — this is a ONE-TIME seed

**DECIDED:** the whole point of this epic is to **abandon the CEO's Excel**. After
the one-time seed, VizzHub is the source of truth: lines are created/edited via the
app (CRUD), the Excel is no longer an input, and the importer pipeline stops running.

Consequences:

- The importer becomes a **seed builder** that runs **once** (local, then replayed in
  prod). No ongoing pipeline, no re-import. **Q-B is therefore best-effort** — there
  is no need for an idempotent natural key, because the row→line match happens exactly
  once with the 15 triage decisions hand-baked in.
- **Drift detection** loses its ongoing job. After the seed there is no Excel to drift
  against. Live "line window/value vs contract" comparison, if still wanted, becomes a
  read-time health signal — **not** a stored `accrual_drift_findings` pipeline. Decide
  during the build whether to keep a lightweight live check or deprecate drift entirely.

Seed builder logic, per Excel row:

1. **Create a line** (`source='excel'`), value from the row, window = `union(linked
   project contract dates, Excel month span)`.
2. **Link projects** per the triage decisions — **by project id** (handles empty /
   duplicate Excel codes natively; no alias table needed).
3. **Render cells** directly, one per Excel month, no range gating; redistribute the
   remainder across the line window.
4. **Unlinked lines** (the 5 triage cases): created with the CEO's Excel name, zero
   project links, window from the Excel span. They render as ordinary grid rows and
   are editable later to link a project.
5. **Team-budget lines.** For an eligible project with budget+dates but no Excel line,
   create a `source='team_budget'` line (window=contract, value=`project.budget`),
   redistributed uniformly.

## 5. Cell ops, redistribute, freeze

- `cell_service.redistribute_for_line(line_id, ...)` replaces
  `redistribute_for_project`. Range = `[line.window_start, line.window_end]`
  (clipped to the open period unless `full_range`). Budget pool = `line.value_eur`.
  Frozen/override semantics unchanged.
- `set_cell_amount` / `clear_override` / `bulk_set_cells` re-key from
  `(project_id, year, month)` to `(line_id, year, month)`.
- **Freeze is unaffected in spirit** — `freeze_period_cells` iterates all cells in
  the cutoff range; it just no longer filters by project. Per-line is transparent.
- New op: `line_service.set_window(line_id, start, end)` — re-runs redistribute for
  the line, never touches frozen cells.

## 6. API changes

- `GET /grid` → **rows are lines**, not projects. Each row carries its linked
  projects (id+code+name) as tags, the window, value_eur, health (Σcells vs
  value_eur), and source. Filtering by project / PM / status / currency operates on
  the *linked* projects; unlinked lines pass when no project filter is set.
- `bounds` derive from line windows (min `window_start` year, max `window_end` year).
- New: `POST /lines`, `PATCH /lines/{id}` (name, window, value, links),
  `DELETE /lines/{id}`, `PATCH /lines/{id}/projects` (link/unlink). All
  `ACCRUAL_MANAGE`.
- Cell endpoints (`PATCH /cells/{id}`, `/redistribute`, `/cells/bulk`) re-keyed to
  line. `redistribute` moves to `POST /lines/{id}/redistribute`.

## 7. Frontend

- **Grid: line-as-row.** Project becomes a tag/filter column (a line can show
  multiple project chips, or none). Overlapping lines on a project are distinct rows.
- **Window editor** per line (dialog or inline date range) — `ACCRUAL_MANAGE` gated
  (`usePermission`/`<Can>` — no dangling affordance for viewers).
- **Create line** action for manual/unlinked revenue.
- **Unlinked lines** render inline as ordinary rows with the CEO's Excel name and a
  "no project" tag; the link-projects action lets a manager attach a project later.
- `buildCellKey` switches from `projectId:year:month` to `lineId:year:month`.
- The Excel-centric `AccrualUnmatched.tsx` page is **retired** along with the
  importer — there is no "unmatched Excel rows" concept once the Excel is abandoned.

## 8. Migration & rollout

The migration must leave a **working app** at every step (we re-seed only at the end).

1. **Schema migration** (Alembic, raw SQL for any enum/constraint per asyncpg rule):
   create `accrual_lines`, `accrual_line_projects`; add `accrual_cells.line_id`
   (nullable first).
2. **Back-fill** a default line per project from existing cells:
   one `source='excel'|'team_budget'` line per `project_id` present in
   `project_accrual_cells`, `value_eur = Σcells`, window = project contract dates,
   one `accrual_line_projects` row, re-key its cells to the new `line_id`.
3. **Tighten**: `line_id` NOT NULL; drop `project_accrual_cells.project_id` and
   rename the table to `accrual_cells`. Drop `accrual_aliases` (retired, Q-A).
4. **Seed builder + API + FE** land behind the new schema. The seed builder is a
   one-shot script (§4), not a recurring pipeline.
5. **One-time seed** on the new model from the live Excel, applying the 15 triage
   decisions **once** (9 linked / 5 unlinked / 1 excluded), then the Excel is
   abandoned. `project_id` UUIDs are stable local↔prod, so the seed replays in prod
   via the established runbook (`accrual-drift-triage`). **Seed once — do not seed
   twice.**

> **Frozen-cell check (gates step 2 vs a clean rebuild):** prod accrual is new
> (seeded 2026-05-24/-29); if **no** periods are closed (no frozen cells), the
> migration can skip the throwaway per-project back-fill and the one-time seed can
> rebuild `accrual_cells` cleanly. If frozen cells exist, they must be preserved as
> frozen lines. **Verify before writing the migration.**

## 9. Decisions (CTO, 2026-05-29)

- **Q-A — DECIDED: retire `accrual_aliases`.** `accrual_line_projects` is the source
  of truth; lines link to projects by id (handles empty/duplicate Excel codes that
  the `excel_code`-keyed alias never could). The alias table is dropped after seed.
- **Q-B — DECIDED: best-effort, one-time.** The row→line match runs only in the seed
  with the triage decisions baked in, so no idempotent natural key is needed (the
  importer is retired — §4).
- **Q-C — `projects.original_budget`. DECIDED: keep it (it is NOT legacy).**
  `original_budget` is the contractual amount in the project's **original currency**
  and becomes the canonical budget field for the whole site in the next epic: at
  project creation, `budget` (EUR) will be **derived** from `original_budget` via the
  CEO's per-period FX rate (see memory `accrual-period-fx-rates`). So accrual keeps
  populating it. The line carries `value_orig`/`currency`/`rate`; for a 1:1 line that
  feeds `project.original_budget`. Multi-project (1:N) lines do **not** split it —
  each linked project keeps its own contractual `original_budget`; TBD how/whether a
  1:N line writes any project's `original_budget` (likely: don't, the project already
  has its own). This is the bridge to the new tracker currency behaviour.
- **Q-D — DECIDED: unlinked lines render inline**, as ordinary grid rows, labelled
  with the name the CEO gave them in the Excel, and **editable later to link a
  project**. No separate section.

## 10. Sub-task slices (proposed)

1. **Schema + back-fill migration** (working app, old importer still runs).
2. **Cell/line services** (`redistribute_for_line`, window ops, re-keyed cell ops) + tests.
3. **Importer rewrite** (lines, no gating, link-by-id, unlinked, team-budget lines) + tests.
4. **API** (grid=lines, line CRUD, re-keyed cell endpoints) + tests.
5. **Frontend** (line-as-row grid, window editor, create-line, unmatched reframe) + tests.
6. **One-time re-seed** + prod replication via runbook.

## 11. Test plan

- Migration round-trip: existing cells re-keyed, totals unchanged (€ sum invariant).
- Overlapping lines on one project keep distinct cells (the problem-#1 regression).
- Out-of-contract Excel months render (the 147-cell case).
- Unlinked line counts toward company total, renders no project tag.
- Window edit re-redistributes, never touches frozen cells.
- Freeze still freezes by `(year, month)` across all lines.
- Health = Σline-cells vs line.value_eur (no FX noise for non-EUR lines).
- Seed parity: re-seed reproduces the 15 triage outcomes (9/5/1).
