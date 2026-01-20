import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConfigParameters, useConfigValidation, useUpdateConfigParameters } from '../useConfig';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useConfig hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useConfigParameters fetches grouped parameters', async () => {
    const mockData = {
      'Targets': [
        {
          id: 1,
          category: 'Targets',
          name: 'DefDensity_t',
          value: '3.0000',
          unit: 'defects/100 tasks',
          notes: 'Target max defect density'
        }
      ],
      'Global Weights': [
        {
          id: 2,
          category: 'Global Weights',
          name: 'W_quality',
          value: '0.1800',
          unit: 'weight',
          notes: 'P_quality'
        }
      ]
    };

    vi.mocked(api.get).mockResolvedValue({ data: mockData });

    const { result } = renderHook(() => useConfigParameters(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(api.get).toHaveBeenCalledWith('/api/config/parameters');
  });

  it('useConfigValidation fetches validation status', async () => {
    const mockData = { valid: true, errors: [] };

    vi.mocked(api.get).mockResolvedValue({ data: mockData });

    const { result } = renderHook(() => useConfigValidation(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(api.get).toHaveBeenCalledWith('/api/config/validate');
  });

  it('useUpdateConfigParameters updates parameters and invalidates queries', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const mockUpdates = [
      { name: 'DefDensity_t', value: '2.5000' }
    ];

    const mockResponse = { message: 'Parameters updated successfully' };
    vi.mocked(api.put).mockResolvedValue({ data: mockResponse });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateConfigParameters(), {
      wrapper,
    });

    result.current.mutate(mockUpdates);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.put).toHaveBeenCalledWith('/api/config/parameters', mockUpdates);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['config'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['scores'] });
  });

  it('useConfigParameters handles API errors', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useConfigParameters(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toEqual(new Error('Network error'));
  });

  it('useConfigValidation handles validation errors', async () => {
    const mockData = {
      valid: false,
      errors: ['Global Weights sum to 0.95, must equal 1.0']
    };

    vi.mocked(api.get).mockResolvedValue({ data: mockData });

    const { result } = renderHook(() => useConfigValidation(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.valid).toBe(false);
    expect(result.current.data?.errors).toHaveLength(1);
  });
});
