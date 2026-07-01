import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PortfolioDashboard from '../PortfolioDashboard';

vi.mock('../../hooks/usePortfolioDashboard', () => ({
  usePortfolioDashboard: () => ({
    isLoading: false,
    data: {
      year: null,
      available_years: [2024, 2025, 2026],
      kpis: { project_count: 42, total_spend_eur: 2_400_000, client_count: 12, avg_margin: 18.3 },
      volume_by_year: [{ year: 2024, count: 10 }],
      spend_by_client: [],
      margin_split: { gain: 20, loss: 5, no_data: 17, avg_margin: 18.3 },
      breakdowns: [{ taxonomy_slug: 'service', taxonomy_name: 'Service Provided', terms: [] }],
    },
  }),
}));

function renderPage(initialEntries?: string[]): void {
  render(
    <MemoryRouter initialEntries={initialEntries || ['/']}>
      <PortfolioDashboard />
    </MemoryRouter>,
  );
}

describe('PortfolioDashboard', () => {
  it('renders KPI values', () => {
    renderPage();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('€2.4M')).toBeInTheDocument();
    expect(screen.getByText('18.3%')).toBeInTheDocument();
  });

  it('shows the empty state for unassigned taxonomy breakdowns', () => {
    renderPage();
    expect(screen.getByText(/No tags assigned yet/i)).toBeInTheDocument();
  });

  it('shows the empty state when no client-linked spend', () => {
    renderPage();
    expect(screen.getByText(/No projects linked to a client yet/i)).toBeInTheDocument();
  });

  it('renders year arrows when year is selected in URL', () => {
    renderPage(['/?year=2025']);
    expect(screen.getByText('2025')).toBeInTheDocument();
  });
});
