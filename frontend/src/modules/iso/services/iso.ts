import type {
  AccessReview,
  AccessReviewActionUpdate,
  AccessReviewDetail,
  AccessReviewUpdate,
  AccessSnapshot,
  AccessSnapshotSummary,
  GitHubIsoConfigStatus,
  IsoConfigStatus,
  PaginatedResponse,
  SignReviewPayload,
} from '../types/iso';
import api from '@/core/services/client';

export interface SnapshotListParams {
  provider?: string;
  page?: number;
  page_size?: number;
}

export interface ReviewListParams {
  status?: string;
  page?: number;
  page_size?: number;
}

export const isoApi = {
  getConfigStatus: async (): Promise<IsoConfigStatus> => {
    const response = await api.get<IsoConfigStatus>(
      '/iso/config/google-workspace',
    );
    return response.data;
  },

  disconnect: async (): Promise<void> => {
    await api.delete('/iso/config/google-workspace/disconnect');
  },

  // GitHub config
  getGitHubConfigStatus: async (): Promise<GitHubIsoConfigStatus> => {
    const response = await api.get<GitHubIsoConfigStatus>(
      '/iso/config/github',
    );
    return response.data;
  },

  saveGitHubOrg: async (orgName: string): Promise<void> => {
    await api.put('/iso/config/github', { org_name: orgName });
  },

  clearGitHubOrg: async (): Promise<void> => {
    await api.delete('/iso/config/github');
  },

  captureSnapshot: async (
    provider: string = 'google_workspace',
  ): Promise<AccessSnapshot> => {
    const response = await api.post<AccessSnapshot>(
      '/iso/snapshots/capture',
      null,
      { params: { provider } },
    );
    return response.data;
  },

  listSnapshots: async (
    params: SnapshotListParams = {},
  ): Promise<PaginatedResponse<AccessSnapshotSummary>> => {
    const response = await api.get<PaginatedResponse<AccessSnapshotSummary>>(
      '/iso/snapshots',
      { params },
    );
    return response.data;
  },

  deleteSnapshot: async (id: string): Promise<void> => {
    await api.delete(`/iso/snapshots/${id}`);
  },

  getSnapshot: async (id: string): Promise<AccessSnapshot> => {
    const response = await api.get<AccessSnapshot>(`/iso/snapshots/${id}`);
    return response.data;
  },

  getSnapshotReview: async (snapshotId: string): Promise<AccessReviewDetail> => {
    const response = await api.get<AccessReviewDetail>(
      `/iso/snapshots/${snapshotId}/review`,
    );
    return response.data;
  },

  listReviews: async (
    params: ReviewListParams = {},
  ): Promise<PaginatedResponse<AccessReview>> => {
    const response = await api.get<PaginatedResponse<AccessReview>>(
      '/iso/reviews',
      { params },
    );
    return response.data;
  },

  getReview: async (id: string): Promise<AccessReviewDetail> => {
    const response = await api.get<AccessReviewDetail>(`/iso/reviews/${id}`);
    return response.data;
  },

  updateReview: async (
    id: string,
    data: AccessReviewUpdate,
  ): Promise<AccessReviewDetail> => {
    const response = await api.patch<AccessReviewDetail>(
      `/iso/reviews/${id}`,
      data,
    );
    return response.data;
  },

  updateAction: async (
    reviewId: string,
    actionId: string,
    data: AccessReviewActionUpdate,
  ): Promise<void> => {
    await api.patch(`/iso/reviews/${reviewId}/actions/${actionId}`, data);
  },

  signReview: async (
    id: string,
    payload?: SignReviewPayload,
  ): Promise<AccessReviewDetail> => {
    const response = await api.post<AccessReviewDetail>(
      `/iso/reviews/${id}/sign`,
      payload,
    );
    return response.data;
  },

  unsignReview: async (id: string): Promise<AccessReviewDetail> => {
    const response = await api.post<AccessReviewDetail>(
      `/iso/reviews/${id}/unsign`,
    );
    return response.data;
  },

  exportSnapshots: async (from: string, to: string, provider?: string): Promise<Blob> => {
    const params: Record<string, string> = { from, to };
    if (provider) params.provider = provider;
    const response = await api.get('/iso/exports/snapshots', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  exportSnapshot: async (id: string): Promise<Blob> => {
    const response = await api.get(`/iso/exports/snapshots/${id}`, {
      responseType: 'blob',
    });
    return response.data;
  },
};
