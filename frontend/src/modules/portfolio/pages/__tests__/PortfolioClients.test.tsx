import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import PortfolioClients from '../PortfolioClients';

const mockUsePermission = vi.fn(() => true);

vi.mock('../../hooks/useClients', () => ({
  useClients: () => ({
    data: {
      items: [
        {
          id: '1',
          name: 'Acme Foundation',
          slug: 'acme-foundation',
          is_active: true,
          project_count: 4,
          created_at: '',
          updated_at: '',
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    },
    isLoading: false,
  }),
  useCreateClient: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateClient: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMergeClients: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockUsePermission>) => mockUsePermission(...args),
}));

function renderPage(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PortfolioClients />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioClients', () => {
  it('renders client rows with project counts', () => {
    mockUsePermission.mockReturnValue(true);
    renderPage();
    expect(screen.getByText('Acme Foundation')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('hides write affordances when user lacks PORTFOLIO_MANAGE', () => {
    mockUsePermission.mockReturnValue(false);
    renderPage();
    expect(screen.queryByText('New client')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });
});
