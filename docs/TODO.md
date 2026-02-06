# TODO / Future Enhancements

## Predictions / Forecasting

Use monthly data points for trend analysis and forecasting:

- [ ] **Leading indicators** - Add predictive metrics: sprint burndown health, blocker age, PR queue depth

- [ ] **Score trend prediction** - Linear regression on monthly scores
  - "If P_quality continues declining, it will be critical in 3 months"

- [ ] **Budget forecast** - Project final cost based on monthly CPI trend
  - "At current burn rate, project will exceed budget by 15%"

- [ ] **Velocity-based estimates** - Forecast completion based on monthly throughput
  - "At current velocity, 45 issues will remain at project end"

- [ ] **Risk prediction** - Early warning based on metric trajectories
  - Combine multiple declining metrics to predict project health

## Visualization Enhancements

- [ ] **Comparative view** - "This month vs last month vs project average"

- [ ] **Monthly health summary** - Dashboard card showing punctual data

## Project Context & Benchmarks

- [ ] **Project context types** - Add classification (greenfield/maintenance/rescue) with adjusted benchmarks per type

- [ ] **Historical benchmarks** - Compare against agency historical averages, not just absolute targets

## Integrations

- [ ] **Team health** - Integrate optional anonymous team surveys (burnout risk, morale)

- [ ] **Technical debt integration** - Connect with SonarQube or similar for code quality tracking

## Key Insight: Punctual vs Cumulative

| Snapshot Type  | Question Answered                    |
| -------------- | ------------------------------------ |
| **Cumulative** | "Where are we?" (current state)      |
| **Punctual**   | "Where are we heading?" (trajectory) |

Punctual captures the **rate of change**, enabling early detection and prediction.
