import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { PeriodEditor } from '@/modules/accrual/components/PeriodEditor';
import { accrualApi } from '@/modules/accrual/services/accrual';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    periods: { list: vi.fn(), current: vi.fn(), create: vi.fn() },
  },
}));

const renderWith = (ui: ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
};

describe('PeriodEditor', () => {
  it('renders the start date input with a default value', () => {
    renderWith(
      <PeriodEditor open onClose={vi.fn()} previousPeriod={null} />,
    );
    const input = screen.getByLabelText(/start date/i) as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.type).toBe('date');
    // Default is the first of the current month — non-empty, ends with -01.
    expect(input.value).toMatch(/^\d{4}-\d{2}-01$/);
  });

  it('shows the freeze note when previousPeriod is set', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1',
          start_date: '2026-01-01',
          status: 'open',
          closed_at: null,
          created_at: '',
          created_by: null,
        }}
      />,
    );
    expect(screen.getByText(/close the current open period/i)).toBeInTheDocument();
  });

  it('does not show freeze note when previousPeriod is null', () => {
    renderWith(
      <PeriodEditor open onClose={vi.fn()} previousPeriod={null} />,
    );
    expect(screen.queryByText(/close the current open period/i)).not.toBeInTheDocument();
  });

  it('renders the Open period button', () => {
    renderWith(
      <PeriodEditor open onClose={vi.fn()} previousPeriod={null} />,
    );
    expect(screen.getByRole('button', { name: /open period/i })).toBeInTheDocument();
  });

  it('Cancel button calls onClose', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor open onClose={onClose} previousPeriod={null} />,
    );
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('submits the start date and calls onClose on success', async () => {
    const onClose = vi.fn();
    vi.mocked(accrualApi.periods.create).mockResolvedValue({
      id: 'p2',
      start_date: '2026-06-01',
      status: 'open',
      closed_at: null,
      created_at: '',
      created_by: null,
    });
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor open onClose={onClose} previousPeriod={null} />,
    );
    const input = screen.getByLabelText(/start date/i) as HTMLInputElement;
    await user.clear(input);
    await user.type(input, '2026-06-01');
    await user.click(screen.getByRole('button', { name: /open period/i }));
    expect(accrualApi.periods.create).toHaveBeenCalledWith({ start_date: '2026-06-01' });
    expect(onClose).toHaveBeenCalled();
  });
});
