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
| 18 | Cost Variance (CV = EV - AC) | not implemented | done | SUSPICIOUS — CV not computed anywhere. budget_variance clamps to ≥0, discarding under-budget signal. Currency assumption undocumented. |
| 19 | Schedule Variance (SV = EV - PV) | not implemented | done | OK — SPI ratio is the substitute and preserves direction (unlike CV's clamped budget_variance). |
| 20 | EAC (Estimate at Completion) | frontend BurnDashboard.tsx:82 (only) | done | SUSPICIOUS — non-EVM time-trend forecast (AC + weighted_burn × remaining_months); ignores CPI/BAC/EV; 0 tests. |
| 21 | ETC (Estimate to Complete) | implicit in EAC only | done | SUSPICIOUS — sister to #20. Not exposed separately; same time-trend formula; refunds + reporting gaps inflate. |
| 22 | percent_completed | tracker/public.py:75-85 | done | OK — manual progress percentage (not hours ratio). DB CHECK + Pydantic enforce 0..1. Latent: stale progress drifts SPI; no test for `_get_latest_progress`. |
| 23 | percent_planned | tracker/public.py:88-101 | done | OK — `(today-start)/(end-start)` clamped [0,1]. None when dates missing or zero-duration. 0 tests covering the helper. |
| 24 | Burn percentage (null if budget=0) | aggregation_service.py:129 / :199 | done | SUSPICIOUS — single vs batch precision divergence; budget=0 vs None conflation; currency assumption silent. |
| 25 | Cost-to-date aggregation | cost_service.py:25-114 + aggregation_service.py | done | SUSPICIOUS — formula is percentage×monthly_rate×dedication×contract/base (NOT hours×rate). base_rate=0 → ZeroDivisionError. Currency gap. Historical freeze correct. |
| 26 | Currency conversion via ECB rates | exchange_rate_service.py | done | SUSPICIOUS — formula+direction correct; missing rate=0 guard, no historical lookup (blocker for #24/#25 fix), no stale-rate warning. |
| 27 | Invoice effective status (CASE SQL) | invoice_status.py:28-54 + invoices.py:56-62 | done | SUSPICIOUS — MAX(postponed_to) instead of most-recent; Python/SQL duplicated logic. CASE branches correct otherwise. |
| 28 | Postponement max date | postponements.py:127-141 | done | SUSPICIOUS — upper bound correct; lower-bound bug allows backdated postponement (due=today-10, postponed_to=today-5 → 201 instead of 400). |
| 29 | Estimated flag exclusion from burn | tracker module-wide | done | OK — all consumers respect "exclude in burn, include in capacity/UI" rule. Latent: mood persists on reopen; mood denominator includes estimated. |
| 30 | Mood aggregation (monthly avg, distribution) | moods.py:38-217 | done | SUSPICIOUS — null-mood + anonymity correct; estimated reports contaminate; trend silently drops current month; 0 tests on /trend. |
| 31 | Period rotation (mid-month, 45-day offset) | worker/rotate_reporting_period.py | done | SUSPICIOUS — double-run on day 15 flips freshly-rotated period to FINISHED. No catch-up if worker down. (45-day offset is FE-only, not backend.) |
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
| 38 | Pydantic Decimal → string parsing (`Number()` before arithmetic) | events/rate types (lying) | done | SUSPICIOUS — events/rate TS types claim `number` but wire is `string`; tracker/scorecard correctly coerce to float server-side. Defensive Number() patches but no tsc safety net. |
| 39 | Chart pagination (max 6 months) | ChartPagination.tsx + 3 chart consumers | done | SUSPICIOUS — math sound; UX bug: default page=0 shows oldest 6 months instead of latest. Zero tests. |

## Stop condition

All rows status=done. Final summary: counts of OK / SUSPICIOUS / WRONG.

## Final summary (2026-05-15)

- **Total audited:** 39/39 rows.
- **OK:** 14 (Scorecard 9 + Tracker 4 + FE 0 + Capacity 0 + intentional-non-impl 1).
- **SUSPICIOUS:** 24 (Scorecard 8 + Tracker 11 + Capacity 4 + FE 1).
- **WRONG:** 1 (#37 formatCurrency — every ISO-4217 currency code renders as € on the FE).

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

