import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useAlertDefinitions,
  useUpdateAlertDefinition,
  useAlertTemplates,
  useScheduledJobs,
  useTriggerScheduledJob,
} from '../useAlertDefinitions';
import { alertsAdminApi, scheduledJobsApi } from '../../services/api';

vi.mock('../../services/api', () => ({
  alertsAdminApi: {
    list: vi.fn(),
    update: vi.fn(),
    getTemplates: vi.fn(),
    updateTemplate: vi.fn(),
  },
  scheduledJobsApi: {
    list: vi.fn(),
    trigger: vi.fn(),
  },
}));

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useAlertDefinitions hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useAlertDefinitions fetches alert definitions', async () => {
    const mockData = [
      {
        id: 1,
        name: 'Budget Alert',
        description: 'Alerts when budget threshold is exceeded',
        category: 'business',
        channel_type: 'leadership',
        schedule: 'daily',
        is_enabled: true,
        config_json: { threshold: 0.9 },
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ];

    vi.mocked(alertsAdminApi.list).mockResolvedValue(mockData);

    const { result } = renderHook(() => useAlertDefinitions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(alertsAdminApi.list).toHaveBeenCalled();
  });

  it('useUpdateAlertDefinition updates an alert', async () => {
    const mockAlert = {
      id: 1,
      name: 'Budget Alert',
      description: 'Alerts when budget threshold is exceeded',
      category: 'business' as const,
      channel_type: 'leadership' as const,
      schedule: 'daily' as const,
      is_enabled: false,
      config_json: { threshold: 0.9 },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
    };

    vi.mocked(alertsAdminApi.update).mockResolvedValue(mockAlert);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateAlertDefinition(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        id: 1,
        data: { is_enabled: false },
      });
    });

    expect(alertsAdminApi.update).toHaveBeenCalledWith(1, { is_enabled: false });
  });

  it('useAlertTemplates fetches templates for an alert', async () => {
    const mockTemplates = [
      {
        id: 1,
        alert_definition_id: 1,
        template_type: 'initial' as const,
        message_template: 'Budget alert: {project_name}',
        is_active: true,
      },
    ];

    vi.mocked(alertsAdminApi.getTemplates).mockResolvedValue(mockTemplates);

    const { result } = renderHook(() => useAlertTemplates(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockTemplates);
    expect(alertsAdminApi.getTemplates).toHaveBeenCalledWith(1);
  });

  it('useAlertTemplates is disabled when alertId is null', () => {
    const { result } = renderHook(() => useAlertTemplates(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(alertsAdminApi.getTemplates).not.toHaveBeenCalled();
  });
});

describe('useScheduledJobs hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useScheduledJobs fetches scheduled jobs', async () => {
    const mockData = [
      {
        name: 'check_dependabot_alerts',
        schedule: 'Daily at 8:00 AM',
        description: 'Checks all projects for new Dependabot alerts',
        last_run: {
          id: 1,
          started_at: '2024-01-15T08:00:00Z',
          completed_at: '2024-01-15T08:05:00Z',
          status: 'completed',
          projects_checked: 10,
          alerts_sent: 2,
          error_message: null,
        },
      },
    ];

    vi.mocked(scheduledJobsApi.list).mockResolvedValue(mockData);

    const { result } = renderHook(() => useScheduledJobs(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(scheduledJobsApi.list).toHaveBeenCalled();
  });

  it('useTriggerScheduledJob triggers a job', async () => {
    const mockResponse = {
      success: true,
      message: 'Job enqueued successfully',
      job_id: 'job-123',
    };

    vi.mocked(scheduledJobsApi.trigger).mockResolvedValue(mockResponse);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useTriggerScheduledJob(), { wrapper });

    await act(async () => {
      const response = await result.current.mutateAsync('check_dependabot_alerts');
      expect(response).toEqual(mockResponse);
    });

    expect(scheduledJobsApi.trigger).toHaveBeenCalledWith('check_dependabot_alerts');
  });
});
