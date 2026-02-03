# TODO / Future Enhancements

## Authentication

- [ ] **Google OAuth** - Implement Google Sign-In for company domain users
  - Install `@react-oauth/google` in frontend
  - Configure Google OAuth client ID in environment
  - Implement login flow in `frontend/src/pages/Login.tsx`
  - Create backend endpoint `POST /api/auth/google` to exchange Google token for JWT
  - Set `DEBUG=false` and `BYPASS_AUTH=false` to enable authentication

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

- [ ] **Trend visualization** - Show score evolution over time, not just snapshots
  - A 70 trending down is worse than 60 trending up

- [ ] **Month-over-month trend charts** - Sparklines showing last 6 months per metric

- [ ] **Comparative view** - "This month vs last month vs project average"

- [ ] **Monthly health summary** - Dashboard card showing punctual data

- [ ] **Automated monthly reports** - Generate stakeholder summaries from punctual data

## Project Context & Benchmarks

- [ ] **Project context types** - Add classification (greenfield/maintenance/rescue) with adjusted benchmarks per type

- [ ] **Historical benchmarks** - Compare against agency historical averages, not just absolute targets

## Integrations

- [ ] **Slack integration** - Connect projects to Slack channels for notifications
  - Add `slack_channel_id` field to projects
  - Slack Bot with `chat:write` permission

- [ ] **Dependabot Slack alerts** - Notify project channels when critical/high vulnerabilities detected
  - Periodic worker task checks GitHub Dependabot API
  - Tracks notified alerts to avoid duplicates
  - Requires Slack integration (above)
  - See `docs/plans/dependabot-slack-alerts.md` for full design

- [ ] **Team health** - Integrate optional anonymous team surveys (burnout risk, morale)

- [ ] **Technical debt integration** - Connect with SonarQube or similar for code quality tracking

## Key Insight: Punctual vs Cumulative

| Snapshot Type | Question Answered |
|---------------|-------------------|
| **Cumulative** | "Where are we?" (current state) |
| **Punctual** | "Where are we heading?" (trajectory) |

Punctual captures the **rate of change**, enabling early detection and prediction.
