import api from './client';

export interface Command {
  id: string;
  module: string;
  action: string;
  target: string | null;
  payload: Record<string, unknown>;
  summary: string;
  status: 'pending' | 'approved' | 'executed' | 'failed' | 'rejected';
  requested_by: string;
  requested_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface CommandListParams {
  status?: string;
  module?: string;
}

export interface ApproveResponse {
  status: 'executed' | 'failed';
  result: Record<string, unknown> | null;
  error: string | null;
}

export const commandsApi = {
  list: async (params: CommandListParams = {}): Promise<Command[]> => {
    const response = await api.get<Command[]>('/commands', { params });
    return response.data;
  },

  approve: async (commandId: string): Promise<ApproveResponse> => {
    const response = await api.post<ApproveResponse>(`/commands/${commandId}/approve`);
    return response.data;
  },

  reject: async (commandId: string): Promise<{ status: 'rejected' }> => {
    const response = await api.post<{ status: 'rejected' }>(`/commands/${commandId}/reject`);
    return response.data;
  },
};
