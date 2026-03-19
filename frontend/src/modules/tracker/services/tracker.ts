import api from '@/core/services/client';
import type {
  ReportingPeriod,
  ReportingPeriodCreate,
  Report,
  ReportWithParts,
  ReportCreate,
  ReportPart,
  ReportPartCreate,
  ReportPartUpdate,
  ProjectCostSummary,
  ProjectReportPart,
  BatchCostsResponse,
  AggregationResponse,
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
};
