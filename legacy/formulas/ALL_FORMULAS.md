# All Formulas Extracted from Project_Scorecard_v3.xlsx

## Data_Forms Sheet

### EVM Calculations
```excel
B13 (EV): =B8*B10
B14 (CPI): =IF(B9>0,B13/B9,NA())
B15 (SPI): =IF(B11>0,B10/B11,NA())
```

### On-Time Milestones
```excel
B24 (OnTimeMilestones_0to1): =SUM(H26:H37)/IF(SUM(G26:G37)=0,NA(),SUM(G26:G37))

-- Per milestone row (example for row 26):
E26 (DueFlag): =IF(OR(C26<>"",TODAY()>B26+GraceDays),1,0)
F26 (OnTimeFlag): =IF(C26<>"",IF(C26<=B26+GraceDays,1,0),IF(TODAY()>B26+GraceDays,0,""))
G26 (WeightUsed): =IF(E26=1,D26,0)
H26 (WeightedOnTime): =F26*D26
```

---

## Params Sheet

### Validators (all should equal 1)
```excel
B31: =SUM(B22:B30)   -- Quality weights
B37: =SUM(B35:B36)   -- Time weights
B43: =SUM(B41:B42)   -- Cost weights
B49: =SUM(B47:B48)   -- Value weights
B55: =SUM(B53:B54)   -- Satisfaction main weights
B64: =SUM(B56:B63)   -- Client survey weights
B71: =SUM(B68:B70)   -- Flow weights
B79: =SUM(B75:B78)   -- Engineering weights
B86: =SUM(B82:B85)   -- Risk weights
B98: =SUM(B90:B97)   -- Global weights
B113: =SUM(B105:B112) -- Test maturity weights
```

---

## Data Sheet

### From Data_Forms (direct references)
```excel
A2 (SPI): =Data_Forms!B15
B2 (OnTimeMilestones): =Data_Forms!B24
C2 (CPI): =Data_Forms!B14
F2 (DefectDensity): =Data_Forms!B49
H2 (EscapedRate): =Data_Forms!B58
I2 (MTTR): =Data_Forms!B68
K2 (LeadTime): =Data_Forms!B111
L2 (FlowEfficiency): =Data_Forms!B120
M2 (CommitmentReliability): =Data_Forms!B129
N2 (PRsWithoutReview): =Data_Forms!B138
O2 (HighVuln): =Data_Forms!B158
P2 (PR_review_ratio): =Data_Forms!B148
```

### Calculated indicators
```excel
D2 (BudgetVariance_OverrunPct):
=IF(Data_Forms!B8=0,0,MAX(0,Data_Forms!B9/Data_Forms!B8 - 1))

E2 (PM_ClientSatisfaction_0to1):
=ROUND(
  0.3*IF(OR(Data_Forms!B87="",Data_Forms!B87="-"),0.75,IF(LOWER(TRIM(Data_Forms!B87))="no",1,IF(LOWER(TRIM(Data_Forms!B87))="yes",0.4,0.75))) +
  0.3*IF(OR(Data_Forms!B88="",Data_Forms!B88="-"),0.75,IF(LOWER(TRIM(Data_Forms!B88))="no",1,IF(LOWER(TRIM(Data_Forms!B88))="yes",0.4,0.75))) +
  0.4*IF(OR(Data_Forms!B89="",Data_Forms!B89="-"),0.5,VALUE(Data_Forms!B89)/5),
2)

G2 (GovernanceCompliance):
=MAX(0, 1 - ( MAX(0, VALUE(Data_Forms!B78)) / MAX(0.000001, VALUE(GovExc_t)) ))

J2 (TestMaturity_percent):
=ROUND(
  W_test_e2e*IF(ISBLANK(Data_Forms!B98),0.5,Data_Forms!B98/5) +
  W_test_unit*IF(ISBLANK(Data_Forms!B99),0.5,Data_Forms!B99/5) +
  W_test_access*IF(ISBLANK(Data_Forms!B100),0.5,Data_Forms!B100/5) +
  W_test_security*IF(ISBLANK(Data_Forms!B101),0.5,Data_Forms!B101/5) +
  W_test_frontend*IF(ISBLANK(Data_Forms!B102),0.5,Data_Forms!B102/5),
2)

Q2 (ArchChecklist_0to4):
=SUM(
  IF(OR(Data_Forms!B167="", LOWER(TRIM(Data_Forms!B167))="select"), 0, VALUE(Data_Forms!B167)),
  IF(OR(Data_Forms!B168="", LOWER(TRIM(Data_Forms!B168))="select"), 0, VALUE(Data_Forms!B168)),
  IF(OR(Data_Forms!B169="", LOWER(TRIM(Data_Forms!B169))="select"), 0, VALUE(Data_Forms!B169)),
  IF(OR(Data_Forms!B170="", LOWER(TRIM(Data_Forms!B170))="select"), 0, VALUE(Data_Forms!B170))
)

R2 (StoriesWithoutReviewer_ratio):
=IFERROR(
  IF(OR(ISBLANK(Data_Forms!B179), Data_Forms!B179=0),
     0,
     MIN(1, MAX(0, Data_Forms!B180 / Data_Forms!B179))
  ),
  0
)

S2 (OKR_Impact_0to100):
-- Google Sheets specific (REGEXMATCH)
=SWITCH(
  TRUE,
  REGEXMATCH(Data_Forms!B190,"(?i)low"), 0.25,
  REGEXMATCH(Data_Forms!B190,"(?i)moderate"), 0.55,
  REGEXMATCH(Data_Forms!B190,"(?i)high"), 0.8,
  REGEXMATCH(Data_Forms!B190,"(?i)transform"), 1,
  0.5
)
```

---

## Scores Sheet

### P_time
```excel
A2:
=ROUND(100*(
  W_time_spi*MIN(1,IF(ISBLANK(Data!A2),0.5,Data!A2/SPI_t)) +
  W_time_milestones*MIN(1,IF(ISBLANK(Data!B2),0.5,Data!B2))
),0)
```

### P_cost
```excel
B2:
=ROUND(100*(
  W_cost_cpi*MIN(1,IF(ISBLANK(Data!C2),0.5,Data!C2/CPI_t)) +
  W_cost_var*MAX(0,IF(ISBLANK(Data!E2),0.5,1-Data!E2))
),0)
```

### P_quality
```excel
C2:
=ROUND(100*(
  W_def * IF(ISBLANK(Data!F2),0.5, MIN(1, DefDensity_t / MAX(Data!F2,0.001))) +
  W_qual_gov * IF(ISBLANK(Data!G2),0.5, Data!G2) +
  W_esc * IF(ISBLANK(Data!H2),0.5, MIN(1, Escaped_t / MAX(Data!H2,0.001))) +
  W_mttr * IF(ISBLANK(Data!I2),0.5, MIN(1, MTTR_t / MAX(Data!I2,0.001))) +
  W_q_pr * IF(ISBLANK(Data!P2),0.5, Data!P2) +
  W_q_storyrev * IF(ISBLANK(Data!R2),0.5, Data!R2)
),0)
```

### P_value
```excel
D2:
=ROUND(100*IF(ISBLANK(Data!S2),0.5,Data!S2/100),0)
```

### P_satisfaction
```excel
E2:
=ROUND(100 * IF(
  NOT(ISBLANK(Data!T2)),
  W_sat_client*Data!T2 + W_sat_pm*IF(ISBLANK(Data!E2),0.5,Data!E2),
  IF(ISBLANK(Data!E2),0.5,Data!E2)
),0)
```

### P_flow
```excel
F2:
=ROUND(100*(
  W_flow_lt*IF(ISBLANK(Data!K2),0.5,MIN(1,LT_t/MAX(Data!K2,0.001))) +
  W_flow_fe*IF(ISBLANK(Data!L2),0.5,MIN(1,Data!L2/FE_t)) +
  W_flow_cr*IF(ISBLANK(Data!M2),0.5,Data!M2)
),0)
```

### P_engineering
```excel
G2:
=ROUND(100 * (
  W_eng_test * IF(ISBLANK(Data!J2), 0.5, Data!J2) +
  W_eng_pr * IF(ISBLANK(Data!P2), 0.5, Data!P2) +
  W_eng_arch * IF(ISBLANK(Data!Q2), 0.5, MIN(1, Data!Q2 / 4))
),0)
```

### P_risk
```excel
H2:
=ROUND(100*(
  W_risk_pr * IF(ISBLANK(Data!N2), 0.5, MAX(0, 1 - Data!N2/PR_noReview_t)) +
  W_risk_vuln * IF(ISBLANK(Data!O2), 0.5, IF(HighVuln_t=0, IF(Data!O2=0,1,0), MAX(0, 1 - Data!O2/HighVuln_t)))
), 0)
```

### Final Score
```excel
B10:
=ROUND(MIN(100,
  W_time*P_time +
  W_cost*P_cost +
  W_quality*P_quality +
  W_value*P_value +
  W_satisfaction*P_satisfaction +
  W_flow*P_flow +
  w_engineering*P_engineering +
  W_risk*P_risk
),0)
```

---

## Named Ranges Required

The formulas reference these named ranges from Params sheet:

**Targets:**
- DefDensity_t, Escaped_t, MTTR_t, SPI_t, CPI_t
- LT_t, FE_t, HighVuln_t, GovExc_t, PR_noReview_t

**Weights:**
- W_time_spi, W_time_milestones
- W_cost_cpi, W_cost_var
- W_def, W_esc, W_mttr, W_q_storyrev, W_qual_gov, W_q_pr
- W_flow_lt, W_flow_fe, W_flow_cr
- W_eng_test, W_eng_pr, W_eng_arch
- W_risk_pr, W_risk_vuln
- W_test_e2e, W_test_unit, W_test_access, W_test_security, W_test_frontend
- W_time, W_cost, W_quality, W_value, W_satisfaction, W_flow, W_engineering, W_risk
- W_sat_client, W_sat_pm

**Dimension scores (as named ranges):**
- P_time, P_cost, P_quality, P_value, P_satisfaction, P_flow, P_engineering, P_risk

**Constants:**
- GraceDays, Sev1_cap
