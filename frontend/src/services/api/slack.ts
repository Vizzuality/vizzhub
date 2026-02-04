import type { SlackChannel } from '../../types';
import api from './client';

export interface SlackConfigResponse {
  id: number;
  bot_token_configured: boolean;
  leadership_channel_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SlackStatusResponse {
  configured: boolean;
}

export interface SlackTestResult {
  ok: boolean;
  team?: string;
  bot_id?: string;
  error?: string;
}

export const slackApi = {
  getStatus: async (): Promise<SlackStatusResponse> => {
    const response = await api.get<SlackConfigResponse>('/admin/slack/config');
    return {
      configured: response.data.bot_token_configured,
    };
  },

  getConfig: async (): Promise<SlackConfigResponse> => {
    const response = await api.get<SlackConfigResponse>('/admin/slack/config');
    return response.data;
  },

  updateConfig: async (data: {
    bot_token?: string;
    leadership_channel_id?: string;
  }): Promise<SlackConfigResponse> => {
    const response = await api.put<SlackConfigResponse>('/admin/slack/config', data);
    return response.data;
  },

  testConnection: async (): Promise<SlackTestResult> => {
    const response = await api.post<SlackTestResult>('/admin/slack/test');
    return response.data;
  },

  getChannels: async (): Promise<SlackChannel[]> => {
    const response = await api.get<SlackChannel[]>('/admin/slack/channels');
    return response.data;
  },
};
