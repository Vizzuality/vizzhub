import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DashboardKpis } from '../DashboardKpis';
import type { DashboardKpis as Kpis } from '@/modules/accrual/types/accrual';

const KPIS: Kpis = {
  recognized_ytd_eur: 12345,
  recognized_quarter_eur: 3000,
  contracted_total_eur: 100000,
  backlog_eur: 87655,
  plan_recognized_pct: 57,
};

describe('DashboardKpis', () => {
  it('renders all four KPI labels and the year-plan-recognized share', () => {
    render(<DashboardKpis kpis={KPIS} />);
    expect(screen.getByText(/Recognized YTD/i)).toBeInTheDocument();
    expect(screen.getByText(/This quarter/i)).toBeInTheDocument();
    expect(screen.getByText(/Backlog/i)).toBeInTheDocument();
    expect(screen.getByText(/Year plan recognized/i)).toBeInTheDocument();
    expect(screen.getByText(/57%/)).toBeInTheDocument();
  });
});
