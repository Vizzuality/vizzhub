import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RateCell } from '../RateCell';
import type { AccrualGridLine } from '@/modules/accrual/types/accrual';

const base = {
  id: 'l1', name: 'L', source: 'manual', excel_code: null,
  value_eur: '1000', value_orig: '1080', currency: 'USD',
  rate: null, period_rate: '1.0800',
  window_start: '2026-01-01', window_end: '2026-03-31',
  projects: [], health: { status: 'ok', diff_eur: null, diff_pct: null },
  data_quality_note: null, dates_diverged: false,
} as AccrualGridLine;

describe('RateCell', () => {
  it('shows the period rate (muted) when there is no override', () => {
    render(<RateCell line={base} canEdit={false} onChange={vi.fn()} />);
    expect(screen.getByText('1.0800')).toBeInTheDocument();
  });

  it('shows an editable line following the period rate in an interactive accent colour (not muted)', () => {
    render(<RateCell line={base} canEdit onChange={vi.fn()} />);
    const el = screen.getByText('1.0800');
    expect(el.className).toMatch(/chart-2/);
    expect(el.className).not.toMatch(/muted-foreground/);
  });

  it('shows the override value with the override colour class', () => {
    render(<RateCell line={{ ...base, rate: '1.2000' }} canEdit={false} onChange={vi.fn()} />);
    const el = screen.getByText('1.2000');
    expect(el.className).toMatch(/score-green/);
  });

  it('shows non-editable 1.0000 for EUR lines', () => {
    render(<RateCell line={{ ...base, currency: 'EUR', value_orig: '1000' }} canEdit onChange={vi.fn()} />);
    expect(screen.getByText('1.0000')).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton')).toBeNull();
  });

  it('submits a new override on blur when editable', async () => {
    const onChange = vi.fn();
    render(<RateCell line={base} canEdit onChange={onChange} />);
    await userEvent.click(screen.getByText('1.0800'));
    const input = screen.getByRole('spinbutton');
    await userEvent.clear(input);
    await userEvent.type(input, '1.2');
    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith('l1', '1.2');
  });

  it('submits null (clear) when the field is emptied', async () => {
    const onChange = vi.fn();
    render(<RateCell line={{ ...base, rate: '1.2000' }} canEdit onChange={onChange} />);
    await userEvent.click(screen.getByText('1.2000'));
    const input = screen.getByRole('spinbutton');
    await userEvent.clear(input);
    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith('l1', null);
  });

  it('cancels without calling onChange when Escape is pressed', async () => {
    const onChange = vi.fn();
    render(<RateCell line={base} canEdit onChange={onChange} />);
    await userEvent.click(screen.getByText('1.0800'));
    const input = screen.getByRole('spinbutton');
    await userEvent.clear(input);
    await userEvent.type(input, '9.99');
    await userEvent.keyboard('{Escape}');
    expect(onChange).not.toHaveBeenCalled();
  });
});
