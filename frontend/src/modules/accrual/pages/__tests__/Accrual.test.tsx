import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Accrual } from '@/modules/accrual/pages/Accrual';

vi.mock('@/modules/accrual/hooks/useAccrualGrid', () => ({
  useAccrualGrid: () => ({
    data: {
      projects: [],
      cells: [],
      months: [{ year: 2026, month: 1 }],
      bounds: null,
      available_currencies: [],
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('@/modules/accrual/hooks/useAccrualMutations', () => ({
  useAccrualMutations: () => ({
    updateCell: vi.fn(),
    bulkUpdate: vi.fn(),
    failedCells: new Set(),
    errorMessage: null,
  }),
}));

vi.mock('@/core/permissions', async () => {
  const actual = await vi.importActual<typeof import('@/core/permissions')>('@/core/permissions');
  return { ...actual, usePermission: () => true };
});

describe('Accrual page', () => {
  it('renders the heading + toolbar', () => {
    render(
      <MemoryRouter>
        <Accrual />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: /accrual grid/i })).toBeInTheDocument();
  });

  it('shows an empty-state message when no projects match', () => {
    render(
      <MemoryRouter>
        <Accrual />
      </MemoryRouter>,
    );
    expect(screen.getByText(/no projects with accrual data in this range/i)).toBeInTheDocument();
  });
});
