# Calculations Audit — Checkpoint

Deep verification of domain math in scorecard + tracker + capacity. One formula per iteration. Findings go to `audit_findings.md` (CALCULATION section).

## How to run

```
/loop Itera revisando docs/audits/audit_calculations.md. Cada vuelta:
1. Lee este checkpoint.
2. Escoge la PRIMERA fila con status=pending.
3. Lanza un Agent que para esa fórmula/cálculo:
   a) Lea la implementación (anota file:line exacto)
   b) Lea la spec/doc relevante (CLAUDE.md "Constraints" section, docs/, comentarios)
   c) Identifique edge cases:
      - null / None inputs
      - división por cero
      - signo (negativo permitido? esperado?)
      - unidades (ratio 0-1 vs porcentaje 0-100, days vs hours, currency)
      - overflow (NUMERIC precision como el CFR bug)
      - timezone (naive vs aware)
      - empty collections
      - currency mismatch / passthrough (rate=1.0)
   d) Verifica tests existentes: ¿cubren los edge cases?
   e) Sugiere 2-3 tests concretos si faltan
4. Anexa veredicto a docs/audits/audit_findings.md sección CALCULATIONS:
   - Status: OK / SUSPICIOUS / WRONG
   - file:line
   - Edge case missed (si aplica)
   - Repro: input → expected vs actual
   - Fix sugerido
5. Marca la fila como status=done.
6. Si quedan pending, sigue. Si todas done, para con un resumen final.
```

## Checkpoint

### Scorecard

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 1 | SPI normalization (target vs ideal) | backend/app/modules/scorecard/services/calculators/time_calculator.py | done | OK — clamp(spi/ideal, 0, 1) × 0.6 + milestones × 0.4. None/0/>ideal/neg/ideal=0 all handled. Tests strong. |
| 2 | CPI normalization | backend/app/modules/scorecard/services/calculators/cost_calculator.py | done | OK — same `_normalize_to_ideal` helper as SPI. Edge cases handled. Tests strong. |
| 3 | budget_variance returning None | indicators.py:88-94 + cost_calculator.py:28-32 | done | OK — rule correctly implemented; all callers handle None. Direct test for the None branch missing (suggested). |
| 4 | Final score weighting | backend/app/modules/scorecard/services/calculators/final_score.py | done | SUSPICIOUS — (a) all-None returns 0 instead of None (rule violation), (b) no runtime weight-sum validation. Fix suggested. |
| 5 | DORA Change Failure Rate | dora.py + collectors/github/change_failure_rate.py | done | SUSPICIOUS — no le=100 on schema, no defensive clamp; column widening (commit 7774abb2) didn't enforce contract. Docstring drift on bands. |
| 6 | DORA deployment frequency | dora.py:141-156 + collectors/github/deployment_frequency.py | done | SUSPICIOUS — Elite `>=1.0` vs docstring "multiple/day"; collector key `release_count_90d` misleading in punctual mode. |
| 7 | DORA lead time | dora.py:158-174 + collectors/jira/lead_time.py:91 | done | SUSPICIOUS — multi-issue: business-vs-calendar day unit mismatch, mean instead of median, UTC-only business window, mislabeled (Jira cycle time, not commit→deploy). |
| 8 | Flow efficiency | flow_calculator.py:26-70 | done | OK — checkpoint premise wrong (no flow_efficiency exists); flow dim is 5-component composite. Calculator clean. Inherits unit caveat from #7. |
| 9 | Quality calculator (bugs ratio, etc.) | quality_calculator.py:7-101 | done | OK — 8 components, weights sum 1.0, units consistent, alerts-toggle rule honored. CFR scale-ambiguity cross-refs #5. |
| 10 | Risk calculator | risk_calculator.py:7-85 | done | SUSPICIOUS — docstring says "target 2%" but seeded default is 10%. Math correct, doc stale. CLAUDE alerts-rule honored. |
| 11 | Satisfaction calculator | satisfaction_calculator.py:27-48 | done | OK — 2 manual components (client 0.90 + pm 0.10), both 0..1 ratios. Zero preserved as real score. |
| 12 | Value calculator | value_calculator.py:27-30 | done | OK — single-component okr_impact passthrough. Latent: unknown enum → NEUTRAL_VALUE 0.5 (unreachable via Pydantic). Dead config row. |
| 13 | Engineering calculator | engineering_calculator.py:24-50 | done | OK — 3 manual components (test_maturity 0.50 + pr_review 0.20 + arch 0.30). Weights 1.00. pr_review has no configurable target (minor asymmetry). |
| 14 | Indicator normalizers | normalizers/indicators.py | done | SUSPICIOUS — 5 normalizers (test_maturity, pm_satisfaction, defect_density, escaped_rate, mttr) violate "missing excluded" rule via 0/0.5 fallbacks. client_survey does it right. |
| 15 | Disabled governance → 0 not neutral | dimensions.py / calc path | done | OK — path B wired: flags gate Slack workers only, badges in UI, scores unaffected. CLAUDE.md already aligned. |
| 16 | Score cache invalidation | score_cache.py + callers | done | SUSPICIOUS — DELETE project doesn't invalidate; cache.set in capture happens before commit (rollback leaves Redis ahead of DB); TOCTOU on concurrent writers. |
| 17 | Global metrics aggregation | global_metrics_service.py:75/134/163 | done | SUSPICIOUS — None-exclusion correct, BUT no status filter (archived projects pollute), equal-weighted, transitively affected by #14. |

### Tracker / EVM

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 18 | Cost Variance (CV = EV - AC) | not implemented | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED (Option B — replace): `IndicatorsCreate.budget_variance` → `cost_variance_pct` (signed); new `normalize_cost_variance` returns 1.0 when CV%≥0, 0.0 when ≤−target, None when input None (per CLAUDE "missing excluded" rule). Migration `072_cv_pct_replaces_bv` renames `target_budget_variance` → `target_cost_variance` idempotently. +5 backend tests. FE label "Cost Variance". Commit `f92ff36b`. **Post-deploy: recalc scorecard history.** |
| 19 | Schedule Variance (SV = EV - PV) | not implemented | done | OK — SPI ratio is the substitute and preserves direction (unlike CV's clamped budget_variance). |
| 20 | EAC (Estimate at Completion) | frontend BurnDashboard.tsx:82 (only) | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: EVM CPI-based forecast (EAC = BAC/CPI = AC/percent_completed) added alongside the time-trend, dashed cool-steel line, legend labels "Forecast (current pace)" + "Forecast (current efficiency)", (i) popover. Pure FE, uses `useProjectProgress`. +16 tests (first BurnDashboard coverage ever). Commit `371b031b`. New finding #40 logged. |
| 21 | ETC (Estimate to Complete) | implicit in EAC only | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: subsumed by #20's EVM forecast — remaining-cost is the gap between EAC_CPI and AC on the chart. Refund/gap inflation in the time-trend forecast still flagged in audit (out of scope for this fix). Commit `371b031b`. |
| 22 | percent_completed | tracker/public.py:75-85 | done | OK — manual progress percentage (not hours ratio). DB CHECK + Pydantic enforce 0..1. Latent: stale progress drifts SPI; no test for `_get_latest_progress`. |
| 23 | percent_planned | tracker/public.py:88-101 | done | OK — `(today-start)/(end-start)` clamped [0,1]. None when dates missing or zero-duration. 0 tests covering the helper. |
| 24 | Burn percentage (null if budget=0) | aggregation_service.py:129 / :199 | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: shared `_compute_burn_percentage` helper (round to 2dp before divide, then round result); explicit `is None or == 0` guard; `currency` field added to `ProjectCostSummary` + `ProjectCostSummaryLite`; FE types additive. +4 regression tests, 2 existing tightened to `==`. Commit `c9071f11`. Cross-currency FX thread-through stays deferred (out of scope). |
| 25 | Cost-to-date aggregation | cost_service.py:25-114 + aggregation_service.py | **fixed 2026-05-16** | ~~SUSPICIOUS (base_rate=0)~~ → FIXED: `Field(gt=0)` on `ReportingPeriodCreate/Update` + DB CHECK via migration `071_period_base_rate_gt0` + `__table_args__` on model. +2 tests. Commit `c4aaeac9`. Currency-mismatch sub-issue still tracked under #24/#26. |
| 26 | Currency conversion via ECB rates | exchange_rate_service.py | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED (3/4 sub-issues): rate=0 guard + None/empty code guard + `as_of: date \| None` historical lookup. +4 regression tests. EUR passthrough preserved. Commit `417aaa4f`. Stale-rate alerting + DB CHECK + Decimal quantize deferred. Unblocks #24/#25. |
| 27 | Invoice effective status (CASE SQL) | invoice_status.py:28-54 + invoices.py:56-62 | **fixed 2026-05-16** | ~~SUSPICIOUS (MAX-vs-most-recent)~~ → FIXED: SQL CASE now uses `ROW_NUMBER() OVER (PARTITION BY invoice_id ORDER BY created_at DESC)` (`postpone_count` preserved via `COUNT() OVER`); Python `_invoice_status_info` uses `ORDER BY created_at DESC LIMIT 1`. +4 regression tests. Commit `9e8661b9`. Python/SQL dedup deferred. |
| 28 | Postponement max date | postponements.py:127-141 | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: lower-bound now `max(base_date, today)`. +3 regression tests in `test_postponements.py`. Commit `f084e0de`. |
| 29 | Estimated flag exclusion from burn | tracker module-wide | done | OK — all consumers respect "exclude in burn, include in capacity/UI" rule. Latent: mood persists on reopen; mood denominator includes estimated. |
| 30 | Mood aggregation (monthly avg, distribution) | moods.py:38-217 | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: `.where(ReportDB.estimated.is_(False))` on both monthly + trend queries. Current-month exclusion pinned by test; first /trend coverage shipped. +5 regression tests, fixture corrected (impossible-state). Commit `f63345a8`. Anti-banker-rounding + named_feedback pagination deferred. |
| 31 | Period rotation (mid-month, 45-day offset) | worker/rotate_reporting_period.py | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: guard `if active and active.date != new_date` prevents flipping the freshly-rotated period. +2 regression tests. Commit `9921bcaf`. Catch-up/missed-15th deferred. |
| 32 | _prepopulate_parts (percentage > 0, status != FINISHED) | reports.py:40 (not period_service) | done | OK — VHUB-124 fix verified. Both filters in place; tests pin them. PROPOSAL status carries by design. |

### Capacity

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 33 | FA breakdown averages | capacity_insights.py:388-417 | done | SUSPICIOUS — partial reporters drag avg, over-reporters not clamped, internal/admin invisible (billable+absence<total silently). |
| 34 | Per-user / per-project percentages | capacity_insights.py:225-271 (user detail) / :116-168 (FA detail) | done | SUSPICIOUS — user detail duplicates same project split across FAs; no gap segment; sum=1.0 only enforced at Confirm. |
| 35 | Reportable users filter | capacity_insights.py + planner.py | done | SUSPICIOUS — 3 leak paths: get_allocation_projects no user filter; planner main query missing reporting filter; user_detail accepts any user_id. |
| 36 | On-leave detection (total report=0) | capacity_insights.py:159/:403/:602 | done | SUSPICIOUS — too narrow: full-PTO reporter (sum=1.0 absence) counted as reporting → drags FA billable avg. |

### Frontend formatters

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 37 | formatCurrency (decimal places, locale) | shared/utils/evmCalculations.ts:25 + modules/tracker/utils/constants.ts:4 | **fixed 2026-05-15** | ~~WRONG~~ → FIXED: ISO-4217 codes now handled. `LEGACY_CURRENCY_MAP` keeps `euro`/`dollar` backward-compat; everything else uppercased and passed to `Intl.NumberFormat` with `ISO_LOCALE_MAP` (EUR/USD/GBP/CHF/JPY/AUD/CAD) + en-US fallback. 9 unit tests added. |
| 38 | Pydantic Decimal → string parsing (`Number()` before arithmetic) | events/rate types (lying) | **fixed 2026-05-16** | ~~SUSPICIOUS~~ → FIXED: Events / Rate Decimal fields now typed as `string` (wire-honest). 2 tsc errors fixed with `Number()` coercion; 1 test mock updated. No latent bugs found — consumer code was already defensive. Tracker/scorecard untouched (already honest server-side). Commit `5319e868`. |
| 39 | Chart pagination (max 6 months) | ChartPagination.tsx + 3 chart consumers | done | SUSPICIOUS — math sound; UX bug: default page=0 shows oldest 6 months instead of latest. Zero tests. |

## Stop condition

All rows status=done. Final summary: counts of OK / SUSPICIOUS / WRONG.

## Fixes log (2026-05-15 PM)

- **#37 formatCurrency** — FE renders ISO-4217 codes correctly. Commit `082fe9d0`.
- **#14 normalizers** — 6 paths now return None on missing data; weights redistributed. Commit `082fe9d0`.
- **#10 risk docstring** — sync with seeded config target. Commit `fbfee1ea`.
- **#5 CFR upper bound** — `le=100` + collector clamp + collector docstring synced with classifier. Commit `fbfee1ea`.
- **#6 DORA deploy freq Elite** — classifier tightened to `> 1.0` (was `>=`). Daily-once → High. Commit `7a1e236d`.
- **#17 global metrics (initial PROPOSAL filter)** — superseded by `8f8a93b6`. Original commit `1c7f39dd`.
- **#4 final-score returns None when all dimensions None** — `int | None`, FE renders `—`. Commit `fd553a13`.
- **#16 score cache holes** — DELETE invalidates; capture endpoint switched from write-through to invalidate (no more cache-ahead-of-DB on rollback). Cache↔cron race deferred (ACCEPT). Commit `3ef06293`.
- **#7 DORA lead-time (mostly)** — business-day thresholds in classifier, median (not mean) in collector, label clarified as Jira cycle time (not DORA Lead Time for Changes). UTC-only business window deferred (ACCEPT). Commit `7399aba4`.
- **#17 stale-snapshot UI** — warning icon next to stale project titles on `/scorecard` index. Commit `4fb88ed5`.
- **#17 weighting policy** — expose equal-weighted AND budget-weighted aggregates side by side. Migration `070_global_by_budget` + `BudgetWeightedScores` schema + service `_average_scores_by_budget` + FE two `GlobalScoreCard`s. Route moved to `/scorecard/global` (user-accessible). Calculate/Recalculate gated to admin. Commit `2efa2c47`.
- **#17 oracle = MetricsDB presence** — dropped status filter entirely. Membership for month M = has a captured row for M. The cron filters status=live upstream, so historical FINISHED rows stay (correct), no spurious future rows (correct). Commit `8f8a93b6`.
- **Post-deploy script** `scripts/recalc_global_history.py` for backfilling legacy `global_metrics` rows with the new logic and the new `_by_budget` columns. Commit `91fa9d78`.
- **#14 addendum (2026-05-16)** — root-cause patch: `_build_evm_data` and `_build_jira_defects` deserializers were silently coercing NULL DB columns to 0, defeating the original #14 fix one layer up. SPI=0/p_time=0/final=0 for brand-new projects (e.g. SKI - maintenance with `percent_completed=NULL`). Now `EVMData` and `JiraDefectMetrics` carry `None` through hydration, and the normalizers guard against it. +9 regression tests. Commit `48b4d961`.
- **Cache flush script** `scripts/invalidate_score_cache.py` for the post-deploy Redis wipe. Shipped with `48b4d961`.
- **SonarCloud cleanup** — `dict.fromkeys` + removed non-native interactive `<span onClick>` in `StaleMetricsIcon`. Commit `988f7cf3`.

## Fixes log (2026-05-16 — Tracker pass)

- **#28 postponement backdate** — lower-bound check now `max(base_date, today)` instead of `base_date`. `backend/app/modules/tracker/api/postponements.py:132-136`. +3 regression tests (`test_postpone_to_past_date_rejected`, `test_postpone_exactly_at_window_boundary`, `test_postpone_when_base_date_is_today`) in `backend/tests/modules/tracker/test_postponements.py`. Commit `f084e0de`. Tracker SUSPICIOUS remaining: 10.
- **#31 period rotation idempotency** — guard tightened from `if active:` to `if active and active.date != new_date:` so a second run on day 15 cannot flip the freshly-rotated period to FINISHED. `backend/app/worker/rotate_reporting_period.py:59`. +2 regression tests (`test_idempotent_second_run_same_day`, `test_active_period_for_current_month_not_finished`) in `backend/tests/test_rotate_reporting_period_job.py`. Commit `9921bcaf`. Tracker SUSPICIOUS remaining: 9. Catch-up/missed-15th deferred (still wants alerting).
- **#25 base_rate=0 ZeroDivisionError** — `Field(gt=0)` on `ReportingPeriodCreate/Update.base_rate`, model `CheckConstraint("base_rate > 0", name="ck_reporting_periods_base_rate_positive")`, migration `071_period_base_rate_gt0` adds the DB CHECK idempotently. +2 regression tests (`test_reporting_period_create_rejects_zero_base_rate`, `…_negative_base_rate`) in `backend/tests/modules/tracker/test_reporting_periods.py`. Commit `c4aaeac9`. Tracker SUSPICIOUS remaining: 8. **Pre-deploy gate:** prod check `SELECT id, date, base_rate FROM reporting_periods WHERE base_rate <= 0` before pushing migration. Currency sub-issue from #25's audit entry stays under #24/#26.
- **#27 invoice effective_status uses most-recent postponement** — SQL CASE in `invoice_status.py:15-46` rewritten with `ROW_NUMBER() OVER (PARTITION BY invoice_id ORDER BY created_at DESC)`; `postpone_count` preserved via `COUNT() OVER`. Python mirror `_invoice_status_info` in `invoices.py:43-72` switched to `ORDER BY created_at DESC LIMIT 1`. +4 regression tests in `test_postponements.py` (`TestEffectiveStatusMostRecent`). Commit `9e8661b9`. Tracker SUSPICIOUS remaining: 7. Python/SQL dedup deferred (out of scope for this fix).
- **#30 mood aggregation excludes estimated reports** — `.where(ReportDB.estimated.is_(False))` on both monthly (`moods.py:90-93`) and trend (`moods.py:149-152`) queries. +5 regression tests in `test_moods.py` (incl. first `/trend` coverage); existing `mood_data` fixture corrected to set `estimated=False` (prior state was production-impossible: mood writes only on Confirm). Commit `f63345a8`. Tracker SUSPICIOUS remaining: 6. Banker's-rounding tweak + named_feedback pagination deferred.
- **#26 exchange_rate_service historical lookup + zero/None guards** — `as_of: date | None` parameter on `get_latest_rate` and `convert_to_eur` (filters `rate_date <= as_of`, EUR passthrough preserved). Rate=0 guard, None/empty code guard, both log structured warning + return None (same semantic as missing-rate). +4 regression tests in `test_exchange_rate_service.py`; 9 legacy tests untouched. Commit `417aaa4f`. **Unblocks the #24/#25 cross-currency thread.** Stale-rate warning, DB `CHECK rate > 0`, Decimal quantize deferred.
- **#24 burn% precision / null guard / currency surfacing** — new `_compute_burn_percentage(total_cost, budget)` helper rounds `total_cost` to 2dp before the divide; both single and batch endpoints use it (same result on identical input). Explicit `if budget is None or budget == 0: return None` makes the rule testable separately. `ProjectCostSummary` + `ProjectCostSummaryLite` carry `currency: str | None` (FE types additive). +4 regression tests in `test_aggregation.py`; 2 existing tests tightened from `pytest.approx(..., abs=0.01)` to `== 7.82` now that precision is unified. Commit `c9071f11`. Tracker SUSPICIOUS remaining: 3 (#18 CV, #20 EAC, #21 ETC — all EVM modernization, need product call). Cross-currency thread-through deferred.

## Fixes log (2026-05-16 — Tracker EVM modernization + FE type honesty)

- **#38 Decimal-as-string TS types** — Events / Rate types relabeled `string`. `EventSummary.{other_costs,total_cost}`, `Attendee.cost`, `EventStats.total_cost`, `Rate.value` all switched. 2 tsc errors surfaced + fixed with `Number()` coercion. 1 test mock updated. **No latent bugs found** — consumer sites were already defensive. Frontend 466 / Backend 1894 green. Commit `5319e868`. Tracker scope: untouched (already honest, backend coerces to float).
- **#20/#21 EAC/ETC EVM forecast** — `BurnDashboard` now shows TWO forecast lines: time-trend (existing) and EVM CPI-based (`EAC = BAC / CPI = AC / percent_completed`). Dashed `coolSteel` line for EVM, solid grey for time-trend. Legend labels: "Forecast (current pace)" + "Forecast (current efficiency)". (i) Info popover with detailed explanation, including formula + when each is more reliable. `useProjectProgress` provides `percent_completed`. Edge cases (pct null/0, BAC null/0, AC=0) gracefully skip the EVM line. +16 tests in new `BurnDashboard.test.tsx` (first BurnDashboard coverage ever). Commit `371b031b`. **New finding #40 surfaced**: `forecastFinal` KPI tile uses un-capped `remainingMonths` but chart line caps at 24 months — UI mismatch on long-tail projects. Logged for follow-up.
- **#18 CV replacing clamped budget_variance** (Option B — CTO approved) — `IndicatorsCreate.budget_variance` → `cost_variance_pct` (signed: `percent_completed × BAC − cost_to_date) / BAC`). New `normalize_cost_variance(cv_pct, target)`: returns None when input None (per CLAUDE "missing excluded" rule), 1.0 when CV%≥0, 0.0 when CV%≤−target, linear between. `CostCalculator` consumes directly (no `1 −` flip). Config row renamed `target_budget_variance` → `target_cost_variance` via migration `072_cv_pct_replaces_bv` (idempotent). FE: `Indicators.cost_variance_pct`, label "Cost Variance" in KpiDashboard. `normalize_budget_variance` retained, marked deprecated. +5 backend tests in `test_calculators.py` + 9 in `test_normalizers.py::TestCostVariance`. Backend 1917 / Frontend 466 green. Commit `f92ff36b`. **Post-deploy: recalc scorecard history.** Migration is data-only on `config_parameters` — no schema change, no row deletion.

## Final summary (2026-05-16 PM — Tracker block closed)

- **Tracker SUSPICIOUS: 0 remaining.** All 11 closed (#18 #20 #21 #24 #25 #26 #27 #28 #30 #31; #29 was OK from the start).
- **Scorecard SUSPICIOUS: 0 remaining.** All 8 closed in earlier pass.
- **Frontend SUSPICIOUS: 1 remaining** (#39 chart default-page).
- **Capacity SUSPICIOUS: 4 remaining** (#33 #34 #35 #36) — need product decision before code.
- **New: #40** (forecastFinal vs chart cap mismatch) — surfaced 2026-05-16 fixing #20/#21.

**Deploy gates:**
1. ~~Prod check before `git push origin dev:main`: `SELECT id, date, base_rate FROM reporting_periods WHERE base_rate <= 0`~~ → **verified `COUNT: 0` 2026-05-16** via SSM + asyncpg on `hub-backend`. Migration `071` safe.
2. ~~Post-deploy: invalidate score cache + recalc scorecard history~~ → **done 2026-05-16 11:46**. `invalidate_score_cache.py` flushed Redis at `redis:6379`. `recalc_global_history.py` ran 2022-06 → 2026-05: 48 months processed, 48 with budget (same coverage as 2026-05-15 run).

**Push + deploy state (2026-05-16):**
- 19 commits pushed to `dev` + `main` (10 fix, 8 docs `[skip ci]`, 1 retrigger).
- First push had `[skip ci]` on HEAD → entire push's CI/CD got suppressed (GitHub behaviour: HEAD-commit `[skip ci]` skips the whole push, not just that commit).
- Deploy triggered manually via `gh workflow run deploy.yml --ref main -f environment=prod`. Run: <https://github.com/Vizzuality/vizzhub/actions/runs/25958451491>. **Deploy succeeded, post-deploy ops complete.**

**Tracker audit fully closed.** Next session: capacity (#33–#36 — product decision pending) + FE #39 (chart default-page) + new #40 (forecastFinal vs chart cap).

## Final summary (2026-05-15, updated 2026-05-16)

- **Total audited:** 39/39 rows.
- **OK:** 14 (unchanged).
- **SUSPICIOUS:** 24 originally; **8 closed** in the scorecard PR pass (all of scorecard's SUSPICIOUS block, some with documented partial scope). **16 still open** (tracker 11, capacity 4, FE 1).
- **WRONG:** 0 (was 1 — #37 formatCurrency, closed 2026-05-15 PM).

Top-priority fixes (smallest diff, highest impact, listed by ROI):

1. #37 `formatCurrency` — accept ISO-4217 keys (case-insensitive) + pass to `Intl.NumberFormat`.
2. #28 postponement — change lower-bound to `max(base_date, today)` instead of `base_date`.
3. #31 period rotation — `if active and active.date != new_date: await finish_period(...)`.
4. #5 CFR — add `le=100` to `IndicatorsCreate.change_failure_rate` + defensive clamp in collector.
5. #25 base_rate=0 — `Field(gt=0)` on `ReportingPeriodCreate.base_rate`.
6. **#14 normalizers cluster (highest-leverage)** — rewrite 5 normalizers to drop None / redistribute weights like `_normalize_client_survey` does; eliminates silent score inflation.
7. #38 TypeScript types — drop the "lying" `number` types on Events / Rate; force tsc to surface every missing `Number(x)`.

Cross-currency family (#18 / #24 / #25 / #26 / #37 / #38) needs `#26 historical-lookup` landed first; then thread `exchange_rate_service` through tracker cost aggregation and invoice rendering.

Capacity findings (#33 / #34 / #35 / #36) share a common root: partial reporters and the missing `internal_pct` segment. Worth treating as a single product decision before code changes.

