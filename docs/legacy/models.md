# Legacy VizzTracker Models Reference

Source: `/Volumes/Work/Dev/Vizz Tracker/vizz_trackr/app/models/`

## State Machines (AASM)

All use `HasStateMachine` concern (provides `next_event`, `next_state`, `with_status(status)` scope).

### Contract
- States: `proposal` (initial) -> `live` -> `finished`
- Events: `start`, `finish`, `restart` (finished->live)

### Invoice
- States: `scheduled` (initial) -> `pending_to_issue` -> `waiting_for_payment` -> `paid`
- Events: `raise_alert` (sends Slack), `issue`, `confirm_payment`

### ReportingPeriod
- States: `unstarted` (initial) -> `active` -> `finished`
- Events: `activate` (deactivates other active periods), `terminate`, `reactivate`
- Only one period can be `active` at a time.

## Models

### User
- **Associations**: belongs_to team (optional), role (optional), rate (optional). has_many reports (dependent: destroy).
- **Devise**: database_authenticatable, recoverable, rememberable, validatable
- **Soft delete**: `destroy` sets `active=false` instead of deleting
- **Fields**: name, email (unique), encrypted_password, reset_password_token, admin (bool), dedication (float, default 0.74), active (bool, default true)
- **Scopes**: `active`, `inactive`
- **Methods**: `current_report` (gets/creates report for active period), `quick_contracts`, `gravatar_url`, `name_with_state`

### Role
- **Associations**: has_many users (nullify), report_parts (nullify), budget_lines (nullify)
- **Fields**: name (unique)
- Job roles (e.g. "Developer", "Designer"), NOT auth roles.

### Team
- **Associations**: has_many users (nullify), reports (nullify)
- **Fields**: name (unique)

### Rate
- **Associations**: has_many users (nullify)
- **Fields**: code (unique), value (float)
- **Methods**: `display` -> "CODE [EUR VALUE]"

### Project
- **Associations**: belongs_to team (optional). has_many contracts (restrict_with_error), project_links (restrict_with_error).
- **Fields**: name (unique, required), is_billable (bool, default true), team_id
- **Methods**: `budget` (sum of contracts), `costs` (sum of burns), `burn_percentage`
- **Nested**: accepts_nested_attributes_for project_links

### ProjectLink
- **Associations**: belongs_to project
- **Fields**: title, url, link_type (enum: code, project-management, app-environments, design)

### Contract
- **Associations**: belongs_to project. has_many report_parts (restrict_with_error), non_staff_costs (destroy), budget_lines (destroy), invoices (destroy), progress_reports (destroy).
- **Fields**: name, code, budget (float), contract_rate (float, default 175.0), start_date, end_date, alias (string array, GIN index), notes (text), summary (text), aasm_state
- **Validations**: start_date after 2018-01-01, end_date after start_date
- **Methods**: `full_name`, `total_burn`, `burn_percentage`, `income_to_date`, `income_percentage`, `budget_left`, `linear_income`, `latest_progress_report`
- **Nested**: accepts_nested_attributes_for budget_lines

### BudgetLine
- **Associations**: belongs_to contract, role (optional)
- **Fields**: days (int), adjusted_days (float), percentage (float), details (string)

### ReportingPeriod
- **Associations**: has_many reports (destroy), non_staff_costs (destroy). has_many report_parts, contracts, users through reports.
- **Fields**: date (unique), base_rate (float, default 175.0), aasm_state
- **Methods**: `active_period` (class), `display_name`, `copy_reports_from(source)`, `to_csv`, `contracts_mean_variance_and_stdev`

### Report
- **Associations**: belongs_to user, team (optional), reporting_period. has_many report_parts (destroy).
- **Fields**: estimated (bool, default false)
- **Nested**: accepts_nested_attributes_for report_parts (allow_destroy)
- **Methods**: `rate` -> reporting_period.base_rate

### ReportPart
- **Associations**: belongs_to report, contract, role (optional)
- **Fields**: percentage (float), days (float), cost (float)
- **Unique index**: (contract_id, report_id, role_id)
- **before_save**: `calculate_cost_and_days` — cost = percentage * rate_value * rate_multiplier / 5.0; days = percentage / 5.0 * dedication
- **rate_multiplier**: contract_rate / reporting_period.base_rate

### ProgressReport
- **Associations**: belongs_to reporting_period, contract
- **Fields**: percentage (float), delta (float)
- **Unique index**: (reporting_period_id, contract_id)
- **Validations**: percentage required, progress can't decrease from previous period
- **before_save**: `calculate_delta` — delta = percentage - previous_percentage; also updates next report's delta

### NonStaffCost
- **Associations**: belongs_to contract, reporting_period
- **Fields**: cost (float, required), cost_type (enum: outsource, travel, servers, others, required), details (string)

### Invoice
- **Associations**: belongs_to contract
- **Fields**: code, amount (float), currency (enum: euro/dollar, default "dollar"), due_date, invoiced_on, extended_date, milestone (text), observations (text), aasm_state
- **Validations**: due_date required, milestone required, amount required (float), code + invoiced_on required when state >= waiting_for_payment
- **Methods**: `send_announcement` (Slack), `must_issue?`

## Views (read-only)

### full_reports
Denormalized JOIN of report_parts + reports + contracts + reporting_periods + teams + users + roles + projects. Used for aggregations and CSV exports.

### monthly_incomes
Calculates income per contract per period: `(contracts.budget * progress_reports.delta) / 100`.

## Key Business Rules

1. **Cost calculation**: ReportPart.cost = percentage * rate_value * (contract_rate / base_rate) / 5.0
2. **Days calculation**: ReportPart.days = percentage / 5.0 * user.dedication
3. **Progress is monotonic**: ProgressReport.percentage can never decrease
4. **Delta tracking**: Each progress report stores its delta from previous; editing old reports cascades delta recalculation
5. **Single active period**: Only one ReportingPeriod can be `active` at a time
6. **Report copying**: New periods can copy reports from a source period (only active users, non-finished contracts)
7. **Budget protection**: Contracts with report_parts cannot be deleted (restrict_with_error)
8. **Soft delete users**: User.destroy sets active=false, preserving historical report data
