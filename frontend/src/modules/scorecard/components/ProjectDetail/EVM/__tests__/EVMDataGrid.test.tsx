import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import EVMDataGrid, { computeCostVariance } from '../EVMDataGrid';
import type { EVMData } from '@/modules/scorecard/types';

const baseEvm: EVMData = {
  budget_total: 100_000,
  cost_to_date: 50_000,
  percent_completed: 0.4,
  percent_planned: 0.5,
};

describe('computeCostVariance', () => {
  it('returns positive CV (under-budget) when EV > AC', () => {
    // EV = 0.4 × 100k = 40k, AC = 30k → CV = +10k, CV% = +10%
    const cv = computeCostVariance({ ...baseEvm, cost_to_date: 30_000 });
    expect(cv).not.toBeNull();
    expect(cv!.value).toBe(10_000);
    expect(cv!.pct).toBeCloseTo(10, 4);
    expect(cv!.tone).toBe('green');
  });

  it('returns negative CV (overrun) when EV < AC', () => {
    // EV = 0.4 × 100k = 40k, AC = 53k → CV = −13k, CV% = −13%
    const cv = computeCostVariance({ ...baseEvm, cost_to_date: 53_000 });
    expect(cv).not.toBeNull();
    expect(cv!.value).toBe(-13_000);
    expect(cv!.pct).toBeCloseTo(-13, 4);
    expect(cv!.tone).toBe('red');
  });

  it('returns null when budget_total is zero', () => {
    expect(computeCostVariance({ ...baseEvm, budget_total: 0 })).toBeNull();
  });

  it('returns null when cost_to_date is zero', () => {
    expect(computeCostVariance({ ...baseEvm, cost_to_date: 0 })).toBeNull();
  });

  it('returns null when percent_completed is null', () => {
    expect(
      computeCostVariance({
        ...baseEvm,
        percent_completed: null as unknown as number,
      }),
    ).toBeNull();
  });
});

describe('EVMDataGrid — Cost Variance tile', () => {
  it('renders the Cost Variance tile alongside the existing four', () => {
    render(<EVMDataGrid evmData={baseEvm} />);
    expect(screen.getByText('Total Budget')).toBeInTheDocument();
    expect(screen.getByText('Actual Cost')).toBeInTheDocument();
    expect(screen.getByText('Work Completed')).toBeInTheDocument();
    expect(screen.getByText('Expected Progress')).toBeInTheDocument();
    expect(screen.getByText('Cost Variance')).toBeInTheDocument();
  });

  it('shows red tone when CV is negative (overrun)', () => {
    render(
      <EVMDataGrid
        evmData={{ ...baseEvm, cost_to_date: 53_000 }}
      />,
    );
    const tile = screen.getByText('Cost Variance').parentElement!;
    const valueEl = tile.querySelector('p.text-2xl');
    expect(valueEl?.className).toContain('text-score-red');
  });

  it('shows green tone when CV is positive (under-budget)', () => {
    render(
      <EVMDataGrid
        evmData={{ ...baseEvm, cost_to_date: 30_000 }}
      />,
    );
    const tile = screen.getByText('Cost Variance').parentElement!;
    const valueEl = tile.querySelector('p.text-2xl');
    expect(valueEl?.className).toContain('text-score-green');
  });

  it('shows — (em dash) when cost_to_date is zero', () => {
    render(<EVMDataGrid evmData={{ ...baseEvm, cost_to_date: 0 }} />);
    const tile = screen.getByText('Cost Variance').parentElement!;
    const valueEl = tile.querySelector('p.text-2xl');
    expect(valueEl?.textContent).toBe('—');
    expect(valueEl?.className).not.toContain('text-score-red');
    expect(valueEl?.className).not.toContain('text-score-green');
  });

  it('shows — when percent_completed is null', () => {
    render(
      <EVMDataGrid
        evmData={{ ...baseEvm, percent_completed: null as unknown as number }}
      />,
    );
    const tile = screen.getByText('Cost Variance').parentElement!;
    const valueEl = tile.querySelector('p.text-2xl');
    expect(valueEl?.textContent).toBe('—');
  });

  it('shows — when budget_total is zero', () => {
    render(<EVMDataGrid evmData={{ ...baseEvm, budget_total: 0 }} />);
    const tile = screen.getByText('Cost Variance').parentElement!;
    const valueEl = tile.querySelector('p.text-2xl');
    expect(valueEl?.textContent).toBe('—');
  });
});
