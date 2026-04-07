import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/modules/scorecard/hooks/useGlobalMetrics', () => ({
  useGlobalMetricsHistory: () => ({ data: [], isLoading: false }),
}));

vi.mock('@/modules/scorecard/hooks/useScores', () => ({
  useScoringConfig: () => ({
    data: {
      targets: { spi: 0.8, cpi: 0.8 },
      global_weights: {
        time: 0.12,
        cost: 0.10,
        quality: 0.20,
        value: 0.05,
        satisfaction: 0.12,
        flow: 0.15,
        engineering: 0.20,
        risk: 0.05,
      },
      ideals: { spi: 1, cpi: 1 },
      constants: { sev1_cap: 60, grace_days: 5 },
      weight_validation: {},
    },
    isLoading: false,
  }),
}));

vi.mock('../../../../hooks/useRegistryRows', () => ({
  useRegistryRows: () => ({ data: [], isLoading: false }),
  useRegistryYears: () => ({ data: [2025] }),
  useCreateRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateRegistryRow: () => ({ mutate: vi.fn() }),
  useDeleteRegistryRow: () => ({ mutate: vi.fn() }),
}));

import KpiDashboard from '../KpiDashboard';

function renderDashboard(isEditor = false): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <KpiDashboard nodeId="test-node-id" isEditor={isEditor} />
    </QueryClientProvider>,
  );
}

describe('KpiDashboard', () => {
  it('renders both sections', () => {
    renderDashboard();

    expect(screen.getByText('FINAL SCORE')).toBeInTheDocument();
    expect(screen.getByText('Global Scorecard')).toBeInTheDocument();
  });

  it('shows cycle selector', () => {
    renderDashboard();

    // The Select trigger should be in the document
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });
});
