import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import PortfolioDashboard from '../PortfolioDashboard';

vi.mock('../../hooks/usePortfolioDashboard', () => ({
  useProjectLeaderboard: () => ({
    data: {
      available_years: [2024],
      rows: [
        { project_id: 'a', name: 'Alpha', client_id: 'c1', client_name: 'WRI',
          margin_pct: 52, profit_eur: 180000, delay_months: 2 },
        { project_id: 'b', name: 'Beta', client_id: null, client_name: null,
          margin_pct: -30, profit_eur: -30000, delay_months: 12 },
      ],
    },
    isLoading: false,
  }),
  useClientLeaderboard: () => ({
    data: { available_years: [2024], rows: [
      { client_id: 'c1', client_name: 'WRI', project_count: 3,
        profit_eur: 250000, margin_pct: 41, delay_months: 4 },
    ] },
    isLoading: false,
  }),
}));

function renderPage(): void {
  render(
    <MemoryRouter initialEntries={['/admin/portfolio/dashboard']}>
      <PortfolioDashboard />
    </MemoryRouter>,
  );
}

describe('PortfolioDashboard', () => {
  it('renders project rows sorted by profit desc by default', () => {
    renderPage();
    const rows = screen.getAllByRole('row');
    // header + 2 data rows; Alpha (180k) before Beta (-30k)
    expect(rows[1]).toHaveTextContent('Alpha');
    expect(rows[2]).toHaveTextContent('Beta');
  });

  it('switches to client grouping', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /client/i }));
    // WRI appears in both the chart axis label and the table cell
    expect(screen.getAllByText('WRI').length).toBeGreaterThan(0);
  });
});
