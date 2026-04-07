import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ManualKpiTable } from '../ManualKpiTable';
import type { RegistryRow } from '../../../types/registry';
import type { MonthColumn } from '../types';

vi.mock('../../../hooks/useRegistryRows', () => ({
  useCreateRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
}));

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const mockRow: RegistryRow = {
  id: 'row-1',
  node_id: 'node-1',
  year: 2025,
  row_index: 0,
  data: {
    name: '% formación seguridad',
    scope: 'Concienciación',
    responsible: 'RRHH',
    methodology: 'Porcentaje de empleados formados',
    formula: 'formados / total',
    target: 0.8,
    periodicity: 'Anual',
    m03: 0.75,
    m04: null,
  },
  created_by_id: null,
  updated_by_id: null,
  created_at: '2025-04-01T00:00:00Z',
  updated_at: '2025-04-01T00:00:00Z',
  attachments: [],
};

const mockMonths: MonthColumn[] = [
  { year: 2025, month: 3, label: 'Mar 2025' },
  { year: 2025, month: 4, label: 'Apr 2025' },
];

describe('ManualKpiTable', () => {
  it('renders manual KPI rows with data', () => {
    render(
      <ManualKpiTable
        nodeId="node-1"
        months={mockMonths}
        rows={[mockRow]}
        isEditor={false}
        selectedYear={2025}
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByText('% formación seguridad')).toBeInTheDocument();
    expect(screen.getByText('Concienciación')).toBeInTheDocument();
    expect(screen.getByText('0.75')).toBeInTheDocument();
  });

  it('shows Add KPI button for editors', () => {
    render(
      <ManualKpiTable
        nodeId="node-1"
        months={mockMonths}
        rows={[]}
        isEditor={true}
        selectedYear={2025}
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByRole('button', { name: /add kpi/i })).toBeInTheDocument();
  });

  it('hides Add KPI button for viewers', () => {
    render(
      <ManualKpiTable
        nodeId="node-1"
        months={mockMonths}
        rows={[]}
        isEditor={false}
        selectedYear={2025}
      />,
      { wrapper: Wrapper },
    );

    expect(screen.queryByRole('button', { name: /add kpi/i })).not.toBeInTheDocument();
  });
});
