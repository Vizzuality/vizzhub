import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  useAlertDefinitions,
  useUpdateAlertDefinition,
  useAlertTemplates,
  useScheduledJobs,
  useTriggerScheduledJob,
} from '../useAlertDefinitions';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useAlertDefinitions hooks', () => {
  it('useAlertDefinitions fetches alert definitions', async () => {
    const { result } = renderHook(() => useAlertDefinitions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([fixtures.alertDefinition]);
  });

  it('useUpdateAlertDefinition updates an alert', async () => {
    let capturedBody: Record<string, unknown> | undefined;

    server.use(
      http.put('/api/admin/alerts/:id', async ({ request, params }) => {
        capturedBody = await request.json() as Record<string, unknown>;
        return HttpResponse.json({
          ...fixtures.alertDefinition,
          id: Number(params.id),
          ...capturedBody,
        });
      }),
    );

    const { result } = renderHook(() => useUpdateAlertDefinition(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        id: 1,
        data: { is_enabled: false },
      });
    });

    expect(capturedBody).toEqual({ is_enabled: false });
  });

  it('useAlertTemplates fetches templates for an alert', async () => {
    const { result } = renderHook(() => useAlertTemplates(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([
      { id: 1, alert_definition_id: 1, channel: 'slack', template: 'Alert: {{metric}}' },
    ]);
  });

  it('useAlertTemplates is disabled when alertId is null', () => {
    const { result } = renderHook(() => useAlertTemplates(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
  });
});

describe('useScheduledJobs hooks', () => {
  it('useScheduledJobs fetches scheduled jobs', async () => {
    const { result } = renderHook(() => useScheduledJobs(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([fixtures.scheduledJob]);
  });

  it('useTriggerScheduledJob triggers a job', async () => {
    const { result } = renderHook(() => useTriggerScheduledJob(), {
      wrapper: createWrapper(),
    });

    let response: unknown;
    await act(async () => {
      response = await result.current.mutateAsync('check_business_alerts');
    });

    expect(response).toEqual({ triggered: true, job_name: 'check_business_alerts' });
  });
});
