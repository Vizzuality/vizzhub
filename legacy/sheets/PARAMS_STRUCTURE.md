# Params Structure

Hoja de configuración con todos los targets, pesos y constantes del sistema.

## 1. Targets (Rows 2-17)

Valores objetivo contra los que se normalizan las métricas.

| Named Range | Value | Unit | Used In | Description |
|-------------|-------|------|---------|-------------|
| DefDensity_t | 3 | defects/100 tasks | P_quality | Max defect density target |
| Escaped_t | 0.01 | escapes/100 tasks | P_quality | Max escaped defects |
| MTTR_t | 24 | hours | P_quality | Max mean time to recover |
| SPI_t | 1 | ratio | P_time | Schedule performance target |
| CPI_t | 1 | ratio | P_cost | Cost performance target |
| LT_t | 3 | days | P_flow | Max lead time |
| FE_t | 0.4 | ratio | P_flow | Target flow efficiency |
| WIP_max | 4 | count | P_flow | Max WIP items (TBI) |
| CFR_max | 0.15 | ratio | - | **Deprecated** |
| ROI_t | 1 | ratio | P_value | ROI target |
| IaC_t | 0.9 | ratio | P_engineering | IaC coverage target |
| HighVuln_t | 0 | count | P_risk | Max high vulns >30d (0=strict) |
| CritRisk_t | 0 | count | P_risk | Max critical overdue risks |
| GovExc_t | 2 | count | P_quality | Max governance exceptions |
| PR_noReview_t | 0.02 | ratio | P_risk | Max PRs without review |

---

## 2. Quality Weights (Rows 20-31)

Pesos para calcular P_quality. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_def | 0.05 | Defect density |
| W_esc | 0.20 | Escaped rate |
| W_mttr | 0.05 | MTTR |
| W_q_storyrev | 0.30 | Stories without reviewer |
| W_qual_gov | 0.30 | Governance compliance |
| W_q_pr | 0.10 | PR review ratio |
| W_q_design | 0 | Design quality (disabled) |
| W_q_science | 0 | Data science (disabled) |

---

## 3. Time Weights (Rows 33-37)

Pesos para calcular P_time. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_time_spi | 0.6 | SPI weight |
| W_time_milestones | 0.4 | On-time milestones weight |

---

## 4. Cost Weights (Rows 39-43)

Pesos para calcular P_cost. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_cost_cpi | 0.7 | CPI weight |
| W_cost_var | 0.3 | Budget variance weight |

---

## 5. Value Weights (Rows 45-49)

Pesos para calcular P_value. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_value_roi | 0.7 | ROI weight (currently unused) |
| W_value_okr | 0.3 | OKR impact weight |

---

## 6. Satisfaction Weights (Rows 51-64)

### Main weights (must sum to 1):
| Named Range | Value | Description |
|-------------|-------|-------------|
| W_sat_client | 0.8 | Client survey weight |
| W_sat_pm | 0.2 | PM estimation weight |

### Client survey question weights (must sum to 1):
| Named Range | Value | Question |
|-------------|-------|----------|
| W_cs_understanding | 0.12 | Understanding needs |
| W_cs_proactivity | 0.12 | Proactivity |
| W_cs_communication | 0.10 | Communication |
| W_cs_time | 0.14 | Delivery time |
| W_cs_response | 0.10 | Response time |
| W_cs_quality | 0.24 | Quality of deliverables |
| W_cs_expect | 0.12 | Met expectations |
| W_cs_recommend | 0.06 | Likely to recommend |

---

## 7. Flow Weights (Rows 66-71)

Pesos para calcular P_flow. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_flow_lt | 0.4 | Lead time weight |
| W_flow_fe | 0.3 | Flow efficiency weight |
| W_flow_cr | 0.3 | Commitment reliability weight |

---

## 8. Engineering Weights (Rows 73-79)

Pesos para calcular P_engineering. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_eng_test | 0.5 | Test maturity weight |
| W_eng_pr | 0.2 | PR review ratio weight |
| W_eng_iac | 0 | IaC coverage (disabled) |
| W_eng_arch | 0.3 | Architecture checklist weight |

---

## 9. Risk Weights (Rows 81-86)

Pesos para calcular P_risk. **Deben sumar 1.**

| Named Range | Value | Description |
|-------------|-------|-------------|
| W_risk_pr | 0.5 | PRs without review |
| W_risk_vuln | 0.5 | High vulns >30d |
| W_risk_risks | 0 | Critical overdue risks (disabled) |

---

## 10. Global Weights (Rows 88-98)

Pesos para el Final Score. **Deben sumar 1.**

| Named Range | Value | Dimension |
|-------------|-------|-----------|
| W_time | 0.12 | P_time |
| W_cost | 0.10 | P_cost |
| W_quality | 0.18 | P_quality |
| W_value | 0.10 | P_value |
| W_risk | 0.05 | P_risk |
| W_flow | 0.15 | P_flow |
| W_engineering | 0.18 | P_engineering |
| W_satisfaction | 0.12 | P_satisfaction |

---

## 11. Gates & Constants (Rows 100-104)

| Named Range | Value | Unit | Description |
|-------------|-------|------|-------------|
| Sev1_cap | 60 | points | Max P_quality if Sev1 incident occurred |
| GraceDays | 3 | days | Grace period for milestone delivery |
| Bonus_max | 0.1 | points | Optional bonus cap (unused) |

---

## 12. Test Maturity Weights (Rows 106-113)

Pesos para calcular TestMaturity_percent. **Deben sumar 1.**

| Named Range | Value | Test Type |
|-------------|-------|-----------|
| W_test_e2e | 0.4 | End-to-end tests |
| W_test_unit | 0.1 | Unit tests |
| W_test_access | 0.1 | Accessibility tests |
| W_test_security | 0.2 | Security tests |
| W_test_frontend | 0.2 | Frontend tests |

---

## Validation Rules

Cada grupo de pesos tiene una celda "validator" que debe mostrar `1`:
```excel
=SUM(weights_range)
```

Si el validator ≠ 1, hay un error de configuración.
