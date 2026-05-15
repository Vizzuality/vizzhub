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
| 1 | SPI normalization (target vs ideal) | backend/app/modules/scorecard/services/calculators/time_calculator.py | pending | Target = green threshold, ideal = 100 pts |
| 2 | CPI normalization | backend/app/modules/scorecard/services/calculators/cost_calculator.py | pending | Same dual-bound logic |
| 3 | budget_variance returning None | backend/app/modules/scorecard/services/calculators/cost_calculator.py | pending | None when cost_to_date ≤ 0 — verify all callers handle |
| 4 | Final score weighting | backend/app/modules/scorecard/services/calculators/final_score.py | pending | Weights must sum to 1.0 per group |
| 5 | DORA Change Failure Rate | backend/app/modules/scorecard/services/calculators/dora.py | pending | Percentage 0-100, NUMERIC(5,2). Check overflow guard |
| 6 | DORA deployment frequency | backend/app/modules/scorecard/services/calculators/dora.py | pending | Frequency unit + null handling |
| 7 | DORA lead time | backend/app/modules/scorecard/services/calculators/dora.py | pending | Median vs avg; days vs hours |
| 8 | Flow efficiency | backend/app/modules/scorecard/services/calculators/flow_calculator.py | pending | Active time / total time, beware /0 |
| 9 | Quality calculator (bugs ratio, etc.) | backend/app/modules/scorecard/services/calculators/quality_calculator.py | pending | |
| 10 | Risk calculator | backend/app/modules/scorecard/services/calculators/risk_calculator.py | pending | |
| 11 | Satisfaction calculator | backend/app/modules/scorecard/services/calculators/satisfaction_calculator.py | pending | |
| 12 | Value calculator | backend/app/modules/scorecard/services/calculators/value_calculator.py | pending | |
| 13 | Engineering calculator | backend/app/modules/scorecard/services/calculators/engineering_calculator.py | pending | |
| 14 | Indicator normalizers | backend/app/modules/scorecard/services/normalizers/indicators.py | pending | Map raw value → 0-100 |
| 15 | Disabled governance → 0 not neutral | backend/app/modules/scorecard/services/calculators/dimensions.py | pending | CLAUDE constraint |
| 16 | Score cache invalidation | backend/app/modules/scorecard/services/score_cache.py | pending | None in tests; race conditions |
| 17 | Global metrics aggregation | backend/app/modules/scorecard/services/global_metrics_service.py | pending | Avg across projects; null handling |

### Tracker / EVM

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 18 | Cost Variance (CV = EV - AC) | backend/app/modules/tracker/services/ | pending | grep for "CV" or "cost_variance" |
| 19 | Schedule Variance (SV = EV - PV) | backend/app/modules/tracker/services/ | pending | |
| 20 | EAC (Estimate at Completion) | backend/app/modules/tracker/services/ | pending | Multiple formulas; which one? |
| 21 | ETC (Estimate to Complete) | backend/app/modules/tracker/services/ | pending | |
| 22 | percent_completed | backend/app/modules/tracker/services/ | pending | hours_logged / hours_budget; cap at 100? |
| 23 | percent_planned | backend/app/modules/tracker/services/ | pending | (today - start) / (end - start); cap? |
| 24 | Burn percentage (null if budget=0) | backend/app/modules/tracker/services/cost_service.py | pending | CLAUDE constraint |
| 25 | Cost-to-date aggregation | backend/app/modules/tracker/services/cost_service.py | pending | Rates × hours; rate band selection |
| 26 | Currency conversion via ECB rates | backend/app/core/services/exchange_rate_service.py | pending | amount / rate; EUR passthrough |
| 27 | Invoice effective status (CASE SQL) | backend/app/modules/tracker/api/invoices.py | pending | pending_to_issue logic; postponement subquery |
| 28 | Postponement max date | backend/app/modules/tracker/services/ | pending | max(base_date, today) + 30 days |
| 29 | Estimated flag exclusion from burn | backend/app/modules/tracker/services/period_service.py | pending | estimated=true excluded from totals |
| 30 | Mood aggregation (monthly avg, distribution) | backend/app/modules/tracker/api/moods.py | pending | Null moods; anonymous separation |
| 31 | Period rotation (mid-month, 45-day offset) | backend/app/modules/tracker/services/period_service.py | pending | |
| 32 | _prepopulate_parts (percentage > 0, status != FINISHED) | backend/app/modules/tracker/services/period_service.py | pending | VHUB-124 fix; verify still holds |

### Capacity

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 33 | FA breakdown averages | backend/app/core/services/capacity_insights.py | pending | TARGET_FA_MAPPING; user filters |
| 34 | Per-user / per-project percentages | backend/app/core/services/capacity_insights.py | pending | Sum must be 100% per user-period |
| 35 | Reportable users filter | backend/app/core/services/capacity_insights.py | pending | requires_project_reporting=false excluded |
| 36 | On-leave detection (total report=0) | backend/app/core/services/capacity_insights.py | pending | |

### Frontend formatters

| # | Calculation | Path | Status | Notes |
|---|-------------|------|--------|-------|
| 37 | formatCurrency (decimal places, locale) | frontend/src/modules/tracker/utils/constants.ts | pending | |
| 38 | Pydantic Decimal → string parsing (`Number()` before arithmetic) | frontend/src/modules/tracker/ | pending | Memory gotcha |
| 39 | Chart pagination (max 6 months) | frontend/src/modules/capacity/components/ | pending | Off-by-one risks |

## Stop condition

All rows status=done. Final summary: counts of OK / SUSPICIOUS / WRONG.
