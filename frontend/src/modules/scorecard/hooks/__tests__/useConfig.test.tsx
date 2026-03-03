import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { useConfigParameters, useConfigValidation, useUpdateConfigParameters } from '../useConfig';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useConfig hooks', () => {
  it('useConfigParameters fetches grouped parameters', async () => {
    const { result } = renderHook(() => useConfigParameters(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(fixtures.configParameters);
  });

  it('useConfigValidation fetches validation status', async () => {
    const { result } = renderHook(() => useConfigValidation(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual({ valid: true, groups: {}, errors: [] });
  });

  it('useUpdateConfigParameters updates parameters and invalidates queries', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const mockUpdates = [{ name: 'DefDensity_t', value: '2.5000' }];

    let capturedBody: unknown;
    server.use(
      http.patch('/api/config/parameters', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ message: 'Parameters updated successfully' });
      }),
    );

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateConfigParameters(), {
      wrapper,
    });

    result.current.mutate(mockUpdates);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedBody).toEqual(mockUpdates);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['config'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['scores'] });
  });

  it('useConfigParameters handles API errors', async () => {
    server.use(
      http.get('/api/config/parameters', () => {
        return HttpResponse.json(
          { detail: 'Network error' },
          { status: 500 },
        );
      }),
    );

    const { result } = renderHook(() => useConfigParameters(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  it('useConfigValidation handles validation errors', async () => {
    server.use(
      http.get('/api/config/validate', () => {
        return HttpResponse.json({
          valid: false,
          errors: ['Global Weights sum to 0.95, must equal 1.0'],
        });
      }),
    );

    const { result } = renderHook(() => useConfigValidation(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toMatchObject({ valid: false });
    expect(result.current.data?.errors).toHaveLength(1);
  });
});
