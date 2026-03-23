export interface ReportingPeriod {
  id: string;
  date: string;
  base_rate: number;
  status: 'unstarted' | 'active' | 'finished';
  report_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReportingPeriodCreate {
  date: string;
  base_rate?: number;
}

export interface Report {
  id: string;
  user_id: string;
  reporting_period_id: string;
  estimated: boolean;
  user_name: string | null;
  user_email: string | null;
  mood: number | null;
  feedback_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportWithParts extends Report {
  parts: ReportPart[];
}

export interface ReportCreate {
  reporting_period_id: string;
  estimated?: boolean;
}

export interface ReportUpdate {
  estimated?: boolean;
  mood?: number | null;
  feedback_text?: string | null;
}

export interface ReportPart {
  id: string;
  report_id: string;
  project_id: string;
  project_name: string | null;
  functional_area_id: string | null;
  percentage: number | null;
  days: number | null;
  cost: number | null;
  created_at: string;
  updated_at: string;
}

export interface ReportPartCreate {
  report_id: string;
  project_id: string;
  functional_area_id?: string;
  percentage: number;
}

export interface ReportPartUpdate {
  functional_area_id?: string | null;
  percentage?: number;
}

export interface PeriodCostBreakdown {
  period_id: string;
  date: string;
  staff_cost: number;
  non_staff_cost: number;
  total: number;
  parts_count: number;
}

export interface ProjectCostSummary {
  project_id: string;
  budget: number | null;
  contract_rate: number;
  staff_cost: number;
  non_staff_cost: number;
  total_cost: number;
  burn_percentage: number | null;
  periods: PeriodCostBreakdown[];
}

export interface ProjectReportPart {
  id: string;
  period_date: string;
  user_name: string | null;
  user_email: string | null;
  functional_area: string | null;
  percentage: number | null;
  days: number | null;
  cost: number | null;
  estimated: boolean;
}

export interface ProjectCostSummaryLite {
  budget: number | null;
  total_cost: number;
  staff_cost: number;
  non_staff_cost: number;
  burn_percentage: number | null;
  income: number;
}

export interface BatchCostsResponse {
  costs: Record<string, ProjectCostSummaryLite>;
  errors: Record<string, string>;
}

export interface AggregationPeriod {
  date: string;
  days: number;
  cost: number;
}

export interface AggregationRow {
  name: string;
  email: string | null;
  total_days: number;
  total_cost: number;
  periods: AggregationPeriod[];
}

export interface AggregationResponse {
  group_by: string;
  rows: AggregationRow[];
}

export interface BudgetLine {
  id: string;
  project_id: string;
  functional_area_id: string | null;
  functional_area_name: string | null;
  days: number | null;
  percentage: number | null;
  details: string | null;
}

export interface BudgetLineCreate {
  functional_area_id: string | null;
  days: number;
  details: string | null;
}

export interface FunctionalArea {
  id: string;
  name: string;
}

export interface ProgressReport {
  id: string;
  reporting_period_id: string;
  project_id: string;
  period_date: string | null;
  percentage: number;
  delta: number | null;
}

export interface ProgressReportCreate {
  reporting_period_id: string;
  percentage: number;
}

export interface ProgressReportUpdate {
  percentage: number;
}

export interface ProgressSummary {
  project_id: string;
  percentage: number;
  delta: number | null;
}

export interface BatchProgressResponse {
  progress: Record<string, ProgressSummary>;
}

export type InvoiceStatus = 'scheduled' | 'pending_to_issue' | 'postponed' | 'waiting_for_payment' | 'paid';

export interface Invoice {
  id: string;
  project_id: string;
  code: string | null;
  amount: number;
  due_date: string;
  invoiced_on: string | null;
  milestone: string;
  observations: string | null;
  status: InvoiceStatus;
  postpone_count: number;
  postponed_to: string | null;
}

export interface InvoiceCreate {
  code?: string | null;
  amount: number;
  due_date: string;
  milestone: string;
  observations?: string | null;
}

export interface AdminInvoice {
  id: string;
  project_id: string;
  project_name: string;
  code: string | null;
  amount: number;
  currency: string;
  due_date: string;
  invoiced_on: string | null;
  milestone: string;
  observations: string | null;
  status: InvoiceStatus;
  postpone_count: number;
  postponed_to: string | null;
}

export interface PaginatedInvoices {
  items: AdminInvoice[];
  total: number;
  page: number;
  pages: number;
}

export interface InvoiceTotals {
  total_pending_eur: number;
  total_postponed_eur: number;
  total_waiting_eur: number;
  total_current_year_eur: number;
  usd_eur_rate: number | null;
  rate_date: string | null;
}

export interface Postponement {
  id: string;
  invoice_id: string;
  postponed_to: string;
  reason: string;
  created_by: string | null;
  created_at: string;
}

export interface AdminInvoiceParams {
  page?: number;
  page_size?: number;
  status?: string;
  project_id?: string;
  search?: string;
  due_from?: string;
  due_to?: string;
  sort_by?: string;
  sort_order?: string;
}

export interface InvoiceUpdate {
  code?: string | null;
  amount?: number;
  due_date?: string;
  invoiced_on?: string | null;
  milestone?: string;
  observations?: string | null;
}

export type NonStaffCostType = 'outsource' | 'travel' | 'servers' | 'others';

export interface NonStaffCost {
  id: string;
  project_id: string;
  reporting_period_id: string;
  cost: number;
  cost_type: string;
  details: string | null;
  created_at: string;
  updated_at: string;
}

export interface NonStaffCostCreate {
  project_id: string;
  reporting_period_id: string;
  cost: number;
  cost_type: NonStaffCostType;
  details?: string | null;
}

export interface NonStaffCostUpdate {
  cost?: number;
  cost_type?: NonStaffCostType;
  details?: string | null;
}

export interface AnonymousFeedbackCreate {
  month: number;
  year: number;
  text: string;
}

export interface AnonymousFeedbackItem {
  id: string;
  text: string;
}

export interface NamedFeedbackItem {
  report_id: string;
  user_name: string;
  mood: number | null;
  text: string | null;
}

export interface MoodsResponse {
  mood_distribution: Record<string, number>;
  total_reports: number;
  total_responses: number;
  average_mood: number | null;
  anonymous_feedback: AnonymousFeedbackItem[];
  named_feedback: NamedFeedbackItem[];
}

export interface TrendMonth {
  month: number;
  year: number;
  label: string;
  average_mood: number | null;
  total_responses: number;
  total_reports: number;
  anonymous_feedback: AnonymousFeedbackItem[];
  named_feedback: NamedFeedbackItem[];
}

export interface MoodsTrendResponse {
  months: TrendMonth[];
}

