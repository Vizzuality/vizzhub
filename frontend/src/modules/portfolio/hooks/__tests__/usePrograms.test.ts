import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import React from 'react';
import { useProgramIndex } from '../usePrograms';
import { portfolioApi } from '../../services/portfolio';

vi.mock('../../services/portfolio', () => ({
  portfolioApi: {
    programs: {
      index: vi.fn().mockResolvedValue({ programs: [], unassigned_projects: [] }),
    },
  },
}));

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  return React.createElement(
    QueryClientProvider,
    { client: new QueryClient({ defaultOptions: { queries: { retry: false } } }) },
    children,
  );
}

describe('useProgramIndex', () => {
  it('fetches with the given filters and keeps previous data across filter changes', async () => {
    const { result, rerender } = renderHook(({ search }) => useProgramIndex({ search }), {
      wrapper,
      initialProps: { search: '' },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    rerender({ search: 'alpha' });
    expect(result.current.data).toBeDefined(); // keepPreviousData: no undefined flash
    expect(portfolioApi.programs.index).toHaveBeenLastCalledWith({ search: 'alpha' });
  });
});
