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
  recognized_prev_ytd_eur: 11000,
  yoy_pct: 12.2,
};

describe('DashboardKpis', () => {
  it('renders all KPI labels and the year-plan-recognized share', () => {
    render(<DashboardKpis kpis={KPIS} />);
    expect(screen.getByText(/Recognized YTD/i)).toBeInTheDocument();
    expect(screen.getByText(/This quarter/i)).toBeInTheDocument();
    expect(screen.getByText(/Backlog/i)).toBeInTheDocument();
    expect(screen.getByText(/Year plan recognized/i)).toBeInTheDocument();
    expect(screen.getByText(/57%/)).toBeInTheDocument();
    expect(screen.getByText(/vs Last Year/i)).toBeInTheDocument();
  });

  it('shows an up arrow and positive percent when YoY is positive', () => {
    render(<DashboardKpis kpis={KPIS} />);
    expect(screen.getByText(/▲ \+12\.2%/)).toBeInTheDocument();
  });

  it('shows a down arrow when YoY is negative', () => {
    render(<DashboardKpis kpis={{ ...KPIS, yoy_pct: -8.4 }} />);
    expect(screen.getByText(/▼ -8\.4%/)).toBeInTheDocument();
  });

  it('falls back to an em-dash when there is no prior-year data', () => {
    render(<DashboardKpis kpis={{ ...KPIS, yoy_pct: null }} />);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/No prior-year data/i)).toBeInTheDocument();
  });
});
