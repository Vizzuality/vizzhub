# TODO / Future Enhancements

## Authentication

- [x] **Google OAuth** - Google Sign-In with domain restriction (@vizzuality.com)

- [ ] **Refactor JWT management** - Move from localStorage to httpOnly cookies for better security

## Alerts System

Use month-over-month comparisons (punctual data) to detect anomalies:

- [ ] **Early warning alerts** - Notifications when metrics cross configurable thresholds

- [ ] **Metric change alerts** - Notify when a metric changes significantly vs previous month
  - Example: "Lead time increased 140% (5 days → 12 days)"
  - Example: "PRs without review: 0 → 8 (possible code review process issue)"

- [ ] **Threshold alerts** - Notify when punctual metrics cross thresholds
  - Example: "Monthly defect density exceeded target"

- [ ] **Trend alerts** - Notify when metrics show consistent decline
  - Example: "P_quality has decreased for 3 consecutive months"

**Why punctual?** Cumulative data dilutes recent changes. A bad month is hidden in project-to-date averages.

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

- [x] **Trend visualization** - Score evolution over time in interactive timeline chart

- [x] **Month-over-month trend charts** - Sparklines showing last 6 months per metric

- [ ] **Comparative view** - "This month vs last month vs project average"

- [ ] **Monthly health summary** - Dashboard card showing punctual data

- [x] **Automated monthly reports** - XLSX export for project scorecard and global dashboard

## Project Context & Benchmarks

- [ ] **Project context types** - Add classification (greenfield/maintenance/rescue) with adjusted benchmarks per type

- [ ] **Historical benchmarks** - Compare against agency historical averages, not just absolute targets

## Integrations

- [x] **Slack integration** - Projects linked to Slack channels, business alerts to leadership channel

- [x] **Dependabot Slack alerts** - Daily cron checks GitHub Dependabot, notifies project channels

- [ ] **Team health** - Integrate optional anonymous team surveys (burnout risk, morale)

- [ ] **Technical debt integration** - Connect with SonarQube or similar for code quality tracking

## Key Insight: Punctual vs Cumulative

| Snapshot Type | Question Answered |
|---------------|-------------------|
| **Cumulative** | "Where are we?" (current state) |
| **Punctual** | "Where are we heading?" (trajectory) |

Punctual captures the **rate of change**, enabling early detection and prediction.
