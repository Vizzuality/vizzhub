import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { AccrualLineEditor } from '@/modules/accrual/components/AccrualLineEditor';
import { accrualApi } from '@/modules/accrual/services/accrual';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    lines: {
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
      linkProject: vi.fn(),
      unlinkProject: vi.fn(),
      redistribute: vi.fn(),
    },
    cells: { upsertOnLine: vi.fn(), clearOverride: vi.fn(), bulk: vi.fn() },
  },
}));

vi.mock('@/core/hooks/useProjects', () => ({
  useAllProjectSummaries: () => ({ data: [] }),
}));

const renderWith = (ui: ReactNode) => {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
};

beforeEach(() => vi.clearAllMocks());

describe('AccrualLineEditor — create mode', () => {
  it('creates a line from the form and closes', async () => {
    vi.mocked(accrualApi.lines.create).mockResolvedValue({ id: 'new-1' } as never);
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWith(<AccrualLineEditor lineId="new" onClose={onClose} />);

    expect(screen.getByText('New accrual line')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Name'), 'Fresh grant');
    const valueInput = screen.getByLabelText('Value €');
    await user.clear(valueInput);
    await user.type(valueInput, '5000');

    await user.click(screen.getByRole('button', { name: /create line/i }));

    await waitFor(() => expect(accrualApi.lines.create).toHaveBeenCalled());
    const payload = vi.mocked(accrualApi.lines.create).mock.calls[0][0];
    expect(payload.name).toBe('Fresh grant');
    expect(String(payload.value_eur)).toBe('5000');
    expect(onClose).toHaveBeenCalled();
  });
});

describe('AccrualLineEditor — edit mode', () => {
  it('seeds the form from the fetched line and saves edits', async () => {
    vi.mocked(accrualApi.lines.get).mockResolvedValue({
      id: 'l1',
      name: 'Existing line',
      source: 'manual',
      excel_code: null,
      value_eur: '500.00',
      value_orig: null,
      currency: 'EUR',
      window_start: '2026-01-01',
      window_end: '2026-12-01',
      projects: [],
    });
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l1' } as never);
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWith(<AccrualLineEditor lineId="l1" onClose={onClose} />);

    const nameInput = await screen.findByDisplayValue('Existing line');
    expect(nameInput).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^save$/i }));
    await waitFor(() => expect(accrualApi.lines.update).toHaveBeenCalledWith('l1', expect.anything()));
    expect(onClose).toHaveBeenCalled();
  });
});
