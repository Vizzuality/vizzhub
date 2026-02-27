import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { useSilences, useCreateSilence, useUpdateSilence, useDeleteSilence } from '../useSilences';
import { server } from '../../test/setup';
import { fixtures } from '../../test/msw-handlers';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSilences hooks', () => {
  it('useSilences fetches active silences', async () => {
    const { result } = renderHook(() => useSilences(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([fixtures.silence]);
  });

  it('useSilences filters by project', async () => {
    let capturedParams: Record<string, string> = {};
    server.use(
      http.get('/api/silences', ({ request }) => {
        const url = new URL(request.url);
        capturedParams = Object.fromEntries(url.searchParams.entries());
        return HttpResponse.json([]);
      }),
    );

    const { result } = renderHook(() => useSilences('proj-123'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedParams.project_id).toBe('proj-123');
    expect(result.current.data).toEqual([]);
  });

  it('useCreateSilence creates a silence', async () => {
    let capturedBody: unknown;
    server.use(
      http.post('/api/silences', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(
          {
            ...fixtures.silence,
            id: 2,
            ...(capturedBody as Record<string, unknown>),
          },
          { status: 201 },
        );
      }),
    );

    const { result } = renderHook(() => useCreateSilence(), {
      wrapper: createWrapper(),
    });

    const payload = {
      project_id: 'proj-123',
      alert_definition_id: null,
      silenced_until: null,
      reason: 'Testing',
    };

    await act(async () => {
      await result.current.mutateAsync(payload);
    });

    expect(capturedBody).toEqual(payload);
  });

  it('useUpdateSilence updates a silence', async () => {
    let capturedBody: unknown;
    let capturedId: string | undefined;
    server.use(
      http.put('/api/silences/:id', async ({ request, params }) => {
        capturedBody = await request.json();
        capturedId = params.id as string;
        return HttpResponse.json({
          ...fixtures.silence,
          id: Number(params.id),
          ...(capturedBody as Record<string, unknown>),
        });
      }),
    );

    const { result } = renderHook(() => useUpdateSilence(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        id: 1,
        data: {
          silenced_until: '2024-03-01T00:00:00Z',
          reason: 'Updated reason',
        },
      });
    });

    expect(capturedId).toBe('1');
    expect(capturedBody).toEqual({
      silenced_until: '2024-03-01T00:00:00Z',
      reason: 'Updated reason',
    });
  });

  it('useDeleteSilence deletes a silence', async () => {
    let capturedId: string | undefined;
    server.use(
      http.delete('/api/silences/:id', ({ params }) => {
        capturedId = params.id as string;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result } = renderHook(() => useDeleteSilence(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(capturedId).toBe('1');
    expect(result.current.isSuccess).toBe(true);
  });
});
