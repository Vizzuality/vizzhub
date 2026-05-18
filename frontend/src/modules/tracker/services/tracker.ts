import api from '@/core/services/client';
import type {
  ReportingPeriod,
  ReportingPeriodCreate,
  Report,
  ReportWithParts,
  ReportCreate,
  ReportUpdate,
  ReportPart,
  ReportPartCreate,
  ReportPartUpdate,
  ProjectCostSummary,
  ProjectReportPart,
  BatchCostsResponse,
  AggregationResponse,
  BudgetLine,
  BudgetLineCreate,
  FunctionalArea,
  ProgressReport,
  ProgressReportCreate,
  ProgressReportUpdate,
  BatchProgressResponse,
  Invoice,
  InvoiceCreate,
  InvoiceUpdate,
  InvoiceStatus,
  AdminInvoice,
  PaginatedInvoices,
  AdminInvoiceParams,
  InvoiceTotals,
  Postponement,
  NonStaffCost,
  NonStaffCostCreate,
  NonStaffCostUpdate,
  AnonymousFeedbackCreate,
  MoodsResponse,
  MoodsTrendResponse,
  ProjectSettings,
  ProjectSettingsUpdate,
  JiraIssuesResponse,
} from '../types/tracker';

export const trackerApi = {
  // Reporting Periods
  listPeriods: async (): Promise<ReportingPeriod[]> => {
    const response = await api.get<ReportingPeriod[]>('/tracker/reporting-periods');
    return response.data;
  },

  createPeriod: async (data: ReportingPeriodCreate): Promise<ReportingPeriod> => {
    const response = await api.post<ReportingPeriod>('/tracker/reporting-periods', data);
    return response.data;
  },

  getPeriod: async (id: string): Promise<ReportingPeriod> => {
    const response = await api.get<ReportingPeriod>(`/tracker/reporting-periods/${id}`);
    return response.data;
  },

  deletePeriod: async (id: string): Promise<void> => {
    await api.delete(`/tracker/reporting-periods/${id}`);
  },

  activatePeriod: async (id: string): Promise<ReportingPeriod> => {
    const response = await api.post<ReportingPeriod>(
      `/tracker/reporting-periods/${id}/activate`,
    );
    return response.data;
  },

  finishPeriod: async (id: string): Promise<ReportingPeriod> => {
    const response = await api.post<ReportingPeriod>(
      `/tracker/reporting-periods/${id}/finish`,
    );
    return response.data;
  },

  reactivatePeriod: async (id: string): Promise<ReportingPeriod> => {
    const response = await api.post<ReportingPeriod>(
      `/tracker/reporting-periods/${id}/reactivate`,
    );
    return response.data;
  },

  // Reports
  listReports: async (periodId: string): Promise<Report[]> => {
    const response = await api.get<Report[]>('/tracker/reports', {
      params: { reporting_period_id: periodId },
    });
    return response.data;
  },

  createReport: async (data: ReportCreate): Promise<Report> => {
    const response = await api.post<Report>('/tracker/reports', data);
    return response.data;
  },

  getReport: async (id: string): Promise<ReportWithParts> => {
    const response = await api.get<ReportWithParts>(`/tracker/reports/${id}`);
    return response.data;
  },

  updateReport: async (id: string, data: ReportUpdate): Promise<Report> => {
    const response = await api.put<Report>(`/tracker/reports/${id}`, data);
    return response.data;
  },

  // Report Parts
  createPart: async (data: ReportPartCreate): Promise<ReportPart> => {
    const response = await api.post<ReportPart>('/tracker/report-parts', data);
    return response.data;
  },

  updatePart: async (id: string, data: ReportPartUpdate): Promise<ReportPart> => {
    const response = await api.put<ReportPart>(`/tracker/report-parts/${id}`, data);
    return response.data;
  },

  deletePart: async (id: string): Promise<void> => {
    await api.delete(`/tracker/report-parts/${id}`);
  },

  // Project Costs
  getProjectCostSummary: async (projectId: string): Promise<ProjectCostSummary> => {
    const response = await api.get<ProjectCostSummary>(
      `/tracker/projects/${projectId}/cost-summary`,
    );
    return response.data;
  },

  getProjectReportParts: async (
    projectId: string,
    periodId?: string,
  ): Promise<ProjectReportPart[]> => {
    const response = await api.get<ProjectReportPart[]>(
      `/tracker/projects/${projectId}/report-parts`,
      { params: periodId ? { period_id: periodId } : undefined },
    );
    return response.data;
  },

  getBatchCosts: async (projectIds: string[]): Promise<BatchCostsResponse> => {
    const response = await api.post<BatchCostsResponse>(
      '/tracker/projects/batch-costs',
      { project_ids: projectIds },
    );
    return response.data;
  },

  getProjectAggregations: async (
    projectId: string,
    groupBy: string,
  ): Promise<AggregationResponse> => {
    const response = await api.get<AggregationResponse>(
      `/tracker/projects/${projectId}/aggregations`,
      { params: { group_by: groupBy } },
    );
    return response.data;
  },

  // Budget Lines
  getBudgetLines: async (projectId: string): Promise<BudgetLine[]> => {
    const response = await api.get<BudgetLine[]>(
      `/tracker/projects/${projectId}/budget-lines`,
    );
    return response.data;
  },

  replaceBudgetLines: async (
    projectId: string,
    lines: BudgetLineCreate[],
  ): Promise<BudgetLine[]> => {
    const response = await api.put<BudgetLine[]>(
      `/tracker/projects/${projectId}/budget-lines`,
      { lines },
    );
    return response.data;
  },

  // Progress Reports
  listProgress: async (projectId: string): Promise<ProgressReport[]> => {
    const response = await api.get<ProgressReport[]>(
      `/tracker/projects/${projectId}/progress`,
    );
    return response.data;
  },

  createProgress: async (
    projectId: string,
    data: ProgressReportCreate,
  ): Promise<ProgressReport> => {
    const response = await api.post<ProgressReport>(
      `/tracker/projects/${projectId}/progress`,
      data,
    );
    return response.data;
  },

  updateProgress: async (
    projectId: string,
    progressId: string,
    data: ProgressReportUpdate,
  ): Promise<ProgressReport> => {
    const response = await api.put<ProgressReport>(
      `/tracker/projects/${projectId}/progress/${progressId}`,
      data,
    );
    return response.data;
  },

  deleteProgress: async (projectId: string, progressId: string): Promise<void> => {
    await api.delete(`/tracker/projects/${projectId}/progress/${progressId}`);
  },

  getBatchProgress: async (projectIds: string[]): Promise<BatchProgressResponse> => {
    const response = await api.post<BatchProgressResponse>(
      '/tracker/projects/batch-progress',
      { project_ids: projectIds },
    );
    return response.data;
  },

  // Invoices
  listInvoices: async (projectId: string): Promise<Invoice[]> => {
    const response = await api.get<Invoice[]>(
      `/tracker/projects/${projectId}/invoices`,
    );
    return response.data;
  },

  createInvoice: async (projectId: string, data: InvoiceCreate): Promise<Invoice> => {
    const response = await api.post<Invoice>(
      `/tracker/projects/${projectId}/invoices`,
      data,
    );
    return response.data;
  },

  updateInvoice: async (
    projectId: string,
    invoiceId: string,
    data: InvoiceUpdate,
  ): Promise<Invoice> => {
    const response = await api.put<Invoice>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}`,
      data,
    );
    return response.data;
  },

  transitionInvoice: async (
    projectId: string,
    invoiceId: string,
    status: InvoiceStatus,
  ): Promise<Invoice> => {
    const response = await api.post<Invoice>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/transition`,
      { status },
    );
    return response.data;
  },

  deleteInvoice: async (projectId: string, invoiceId: string): Promise<void> => {
    await api.delete(`/tracker/projects/${projectId}/invoices/${invoiceId}`);
  },

  // Admin Invoices
  listAllInvoices: async (params: AdminInvoiceParams): Promise<PaginatedInvoices> => {
    const response = await api.get<PaginatedInvoices>('/tracker/invoices', { params });
    return response.data;
  },

  getAdminInvoice: async (invoiceId: string): Promise<AdminInvoice> => {
    const { data } = await api.get<AdminInvoice>(`/tracker/invoices/${invoiceId}`);
    return data;
  },

  getInvoiceTotals: async (): Promise<InvoiceTotals> => {
    const { data } = await api.get<InvoiceTotals>('/tracker/invoices/totals');
    return data;
  },

  postponeInvoice: async (
    projectId: string,
    invoiceId: string,
    body: { postponed_to: string; reason: string },
  ): Promise<Postponement> => {
    const { data } = await api.post<Postponement>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postpone`,
      body,
    );
    return data;
  },

  listPostponements: async (projectId: string, invoiceId: string): Promise<Postponement[]> => {
    const { data } = await api.get<Postponement[]>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postponements`,
    );
    return data;
  },

  deleteLatestPostponement: async (projectId: string, invoiceId: string): Promise<void> => {
    await api.delete(`/tracker/projects/${projectId}/invoices/${invoiceId}/postponements/latest`);
  },

  approvePostponement: async (
    projectId: string,
    invoiceId: string,
    postponementId: string,
    body?: { note?: string },
  ): Promise<Postponement> => {
    const { data } = await api.post<Postponement>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postponements/${postponementId}/approve`,
      body ?? {},
    );
    return data;
  },

  rejectPostponement: async (
    projectId: string,
    invoiceId: string,
    postponementId: string,
    body: { note: string },
  ): Promise<Postponement> => {
    const { data } = await api.post<Postponement>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postponements/${postponementId}/reject`,
      body,
    );
    return data;
  },

  cancelPostponement: async (
    projectId: string,
    invoiceId: string,
    postponementId: string,
  ): Promise<Postponement> => {
    const { data } = await api.post<Postponement>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postponements/${postponementId}/cancel`,
    );
    return data;
  },

  // Non-Staff Costs
  listNonStaffCosts: async (projectId: string): Promise<NonStaffCost[]> => {
    const { data } = await api.get<NonStaffCost[]>('/tracker/non-staff-costs', {
      params: { project_id: projectId },
    });
    return data;
  },

  createNonStaffCost: async (payload: NonStaffCostCreate): Promise<NonStaffCost> => {
    const { data } = await api.post<NonStaffCost>('/tracker/non-staff-costs', payload);
    return data;
  },

  updateNonStaffCost: async (costId: string, payload: NonStaffCostUpdate): Promise<NonStaffCost> => {
    const { data } = await api.put<NonStaffCost>(`/tracker/non-staff-costs/${costId}`, payload);
    return data;
  },

  deleteNonStaffCost: async (costId: string): Promise<void> => {
    await api.delete(`/tracker/non-staff-costs/${costId}`);
  },

  // Moods & Feedback
  createAnonymousFeedback: async (data: AnonymousFeedbackCreate): Promise<void> => {
    await api.post('/tracker/anonymous-feedback', data);
  },

  getMoods: async (month: number, year: number): Promise<MoodsResponse> => {
    const { data } = await api.get<MoodsResponse>('/tracker/moods', {
      params: { month, year },
    });
    return data;
  },

  deleteAnonymousFeedback: async (id: string): Promise<void> => {
    await api.delete(`/tracker/moods/anonymous/${id}`);
  },

  deleteReportMood: async (reportId: string): Promise<void> => {
    await api.delete(`/tracker/moods/report/${reportId}/mood`);
  },

  getMoodsTrend: async (): Promise<MoodsTrendResponse> => {
    const { data } = await api.get<MoodsTrendResponse>('/tracker/moods/trend');
    return data;
  },

  // Project Settings
  getProjectSettings: async (projectId: string): Promise<ProjectSettings> => {
    const { data } = await api.get<ProjectSettings>(
      `/tracker/projects/${projectId}/settings`,
    );
    return data;
  },

  updateProjectSettings: async (
    projectId: string,
    body: ProjectSettingsUpdate,
  ): Promise<ProjectSettings> => {
    const { data } = await api.put<ProjectSettings>(
      `/tracker/projects/${projectId}/settings`,
      body,
    );
    return data;
  },

  // Functional Areas
  listFunctionalAreas: async (): Promise<FunctionalArea[]> => {
    const response = await api.get<FunctionalArea[]>('/functional-areas');
    return response.data;
  },

  // Currencies
  listCurrencies: async (): Promise<string[]> => {
    const { data } = await api.get<string[]>('/currencies');
    return data;
  },

  // Jira issues for report
  getJiraIssues: async (periodDate: string): Promise<JiraIssuesResponse> => {
    const { data } = await api.get<JiraIssuesResponse>('/tracker/jira-issues', {
      params: { period_date: periodDate },
    });
    return data;
  },
};
