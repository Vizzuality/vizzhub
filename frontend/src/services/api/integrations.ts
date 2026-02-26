import type { SlackChannel } from '../../types';
import api from './client';

export interface ProviderStatus {
  connected: boolean;
  expires_at: string | null;
  token_type: string | null;
  site_url: string | null;
  created_at: string | null;
}

export interface AllIntegrationsStatus {
  jira: ProviderStatus;
  google_workspace: ProviderStatus;
  github: ProviderStatus;
  slack: ProviderStatus;
  slack_settings: {
    leadership_channel_id: string | null;
  };
}

export interface SlackTestResult {
  ok: boolean;
  team?: string;
  bot_id?: string;
  error?: string;
}

export const integrationsApi = {
  getStatus: async (): Promise<AllIntegrationsStatus> => {
    const response = await api.get<AllIntegrationsStatus>('/admin/integrations/status');
    return response.data;
  },

  saveGitHubToken: async (token: string): Promise<ProviderStatus> => {
    const response = await api.put<ProviderStatus>('/admin/integrations/github', { token });
    return response.data;
  },

  deleteGitHub: async (): Promise<void> => {
    await api.delete('/admin/integrations/github');
  },

  saveSlackToken: async (token: string): Promise<ProviderStatus> => {
    const response = await api.put<ProviderStatus>('/admin/integrations/slack', { token });
    return response.data;
  },

  deleteSlack: async (): Promise<void> => {
    await api.delete('/admin/integrations/slack');
  },

  updateSlackSettings: async (data: {
    leadership_channel_id?: string;
  }): Promise<{ leadership_channel_id: string | null }> => {
    const response = await api.put('/admin/integrations/slack/settings', data);
    return response.data;
  },

  getSlackChannels: async (): Promise<SlackChannel[]> => {
    const response = await api.get<SlackChannel[]>('/admin/integrations/slack/channels');
    return response.data;
  },

  testSlackConnection: async (): Promise<SlackTestResult> => {
    const response = await api.post<SlackTestResult>('/admin/integrations/slack/test');
    return response.data;
  },
};
