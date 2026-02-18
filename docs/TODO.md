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

## Hub ISO Module (`app/modules/iso/`)

New Hub module for ISO compliance management. Centralizes records, evidence collection, and audit readiness. Follows the same modular architecture as Scorecard and Tracker (`docs/vizztracker_integration.md`).

### Access Reviews (Monthly)

Automated monthly snapshots of privileged access across all systems. Read-only collectors, diffs against previous month, evidence reports.

#### Collectors (read-only)

- [ ] **AWS Identity Center** — Privileged access groups & permission sets (Admin, PowerUser, Prod-write); membership + assignments
  - API: `identitystore:List*`, `sso-admin:List*` (read-only, uses EC2 IAM role)

- [ ] **GitHub** — Org owners, repo admins, write access to critical repos; teams/members + external collaborators
  - API: `read:org`, `read:members` scope (read-only token)

- [ ] **Google Workspace** — Super-admins and security/admin groups; group members
  - API: OAuth with admin account, scopes `admin.directory.group.readonly` + `admin.directory.user.readonly` — no domain-wide delegation

- [ ] **Atlassian (Jira/Confluence)** — Global admins and admin groups; members
  - API: `read:jira-user`, `read:confluence-user` (read-only OAuth scopes)

- [ ] **External users (freelancers/vendors)** — All external accounts with access to repos/tooling; end date and scope

#### Diff & Evidence

- [ ] **Diff engine** — Compare current snapshot vs previous month; flag high-risk changes (new admins/owners, new externals, admin overrides)

- [ ] **Evidence report** — 1-page "Access Review Report" (markdown/PDF) + evidence bundle (CSVs, diffs) stored as ISO records

#### KPI

- [ ] **Access reviews completed on time** (per month) + count of privileged changes (adds/removals)

### ISO Records & Evidence

- [ ] **Export for ISO compliance** — Generate reports/exports formatted for ISO audit requirements

- [ ] **Management review cadence** — Scheduled management review cycles with evidence tracking

- [ ] **Customer satisfaction coverage** — Satisfaction metrics tracking and reporting

- [ ] **Non-conformity register** — Track non-conformities, corrective actions, and closure status

- [ ] **Document control** — Version-controlled policy/procedure records with review dates

- [ ] **Internal audit log** — Track internal audit schedule, findings, and follow-ups

### Credential Management

- [ ] **Admin-configurable OAuth secrets** — Store `client_id`/`client_secret` per provider in DB, manageable from the admin UI (same pattern as Slack config). No env vars, no redeploy to rotate. Covers Google, Atlassian, and GitHub App credentials.

### Architecture

```
app/modules/iso/
  models/             # DB models: access_snapshots, reviews, records, evidence
  services/
    collectors/       # aws.py, github.py, google.py, atlassian.py
    diff_engine.py    # Compare snapshots
    report.py         # Generate reports
  api/                # Endpoints: reviews, records, evidence, admin config
  public.py           # Cross-module interface

src/modules/iso/
  components/         # UI: review dashboard, records, evidence viewer
  hooks/              # Data fetching
  pages/              # Routes
```

### Prerequisites (outside this project)

- [ ] **Organization Trail (CloudTrail → S3)** — Enable in the management account to capture IAM/Identity Center events from all subaccounts. First trail is free, S3 cost negligible. Without it, AWS audit logs expire at 90 days. Managed under org-level Terraform, not this project.

### Future

- Auto-create Jira tickets for flagged access changes with 7-day SLA
- Slack reminders until closed
- Risk assessment register
- Supplier evaluation records

## Key Insight: Punctual vs Cumulative

| Snapshot Type  | Question Answered                    |
| -------------- | ------------------------------------ |
| **Cumulative** | "Where are we?" (current state)      |
| **Punctual**   | "Where are we heading?" (trajectory) |

Punctual captures the **rate of change**, enabling early detection and prediction.
