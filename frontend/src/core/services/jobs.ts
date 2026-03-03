import type {
  CreateCaptureHistoryJobRequest,
  JobDetailResponse,
  JobResponse,
  JobSummaryResponse,
} from '@/types';
import api from './client';

export const jobsApi = {
  createCaptureHistory: async (
    request: CreateCaptureHistoryJobRequest,
  ): Promise<JobResponse> => {
    const response = await api.post<JobResponse>('/jobs/capture-history', request);
    return response.data;
  },

  getJob: async (jobId: string): Promise<JobDetailResponse> => {
    const response = await api.get<JobDetailResponse>(`/jobs/${jobId}`);
    return response.data;
  },

  listJobs: async (projectId?: string): Promise<JobSummaryResponse[]> => {
    const params = projectId ? { project_id: projectId } : {};
    const response = await api.get<JobSummaryResponse[]>('/jobs', { params });
    return response.data;
  },

  cancelJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/cancel`);
    return response.data;
  },

  retryJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/retry`);
    return response.data;
  },

  deleteJob: async (jobId: string): Promise<void> => {
    await api.delete(`/jobs/${jobId}`);
  },
};
