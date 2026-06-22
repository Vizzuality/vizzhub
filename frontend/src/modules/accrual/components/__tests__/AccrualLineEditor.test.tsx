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
      setRate: vi.fn(),
    },
    cells: { upsertOnLine: vi.fn(), clearOverride: vi.fn(), bulk: vi.fn() },
  },
}));

let mockCanUnlock = true;
vi.mock('@/core/permissions', async () => {
  const actual = await vi.importActual<typeof import('@/core/permissions')>('@/core/permissions');
  return { ...actual, usePermission: () => mockCanUnlock };
});

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
    // Save keeps the sheet open (so the user can redistribute next) and shows feedback.
    expect(await screen.findByRole('status')).toHaveTextContent(/saved/i);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('Close button closes the sheet without saving', async () => {
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
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWith(<AccrualLineEditor lineId="l1" onClose={onClose} />);
    await screen.findByDisplayValue('Existing line');

    // Two buttons read "Close": the Sheet's built-in X (rendered first) and the
    // footer button. Target the footer one (last).
    const closeButtons = screen.getAllByRole('button', { name: /^close$/i });
    await user.click(closeButtons[closeButtons.length - 1]);
    expect(onClose).toHaveBeenCalled();
    expect(accrualApi.lines.update).not.toHaveBeenCalled();
  });

  it('sends the FX override only when the rate field changes', async () => {
    vi.mocked(accrualApi.lines.get).mockResolvedValue({
      id: 'l2',
      name: 'USD line',
      source: 'manual',
      excel_code: null,
      value_eur: '1000.00',
      value_orig: '1080.00',
      currency: 'USD',
      rate: null,
      period_rate: '1.0800',
      window_start: '2026-01-01',
      window_end: '2026-03-31',
      projects: [],
    });
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l2' } as never);
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWith(<AccrualLineEditor lineId="l2" onClose={onClose} />);

    const rateInput = await screen.findByLabelText('Rate (FX override)');
    await user.type(rateInput, '1.2');
    await user.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => expect(accrualApi.lines.update).toHaveBeenCalled());
    const [, payload] = vi.mocked(accrualApi.lines.update).mock.calls[0];
    expect(payload.rate).toBe('1.2');
  });

  it('omits the rate from the payload when the field is untouched', async () => {
    vi.mocked(accrualApi.lines.get).mockResolvedValue({
      id: 'l3',
      name: 'USD line',
      source: 'manual',
      excel_code: null,
      value_eur: '1000.00',
      value_orig: '1080.00',
      currency: 'USD',
      rate: '1.0800',
      period_rate: '1.0800',
      window_start: '2026-01-01',
      window_end: '2026-03-31',
      projects: [],
    });
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l3' } as never);
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWith(<AccrualLineEditor lineId="l3" onClose={onClose} />);
    await screen.findByDisplayValue('USD line');
    await user.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => expect(accrualApi.lines.update).toHaveBeenCalled());
    const [, payload] = vi.mocked(accrualApi.lines.update).mock.calls[0];
    expect(payload).not.toHaveProperty('rate');
  });
});

describe('AccrualLineEditor — unlock frozen cells', () => {
  const EDIT_LINE = {
    id: 'l1',
    name: 'Frozen line',
    source: 'manual',
    excel_code: null,
    value_eur: '1200.00',
    value_orig: null,
    currency: 'EUR',
    rate: null,
    period_rate: null,
    window_start: '2026-01-01',
    window_end: '2026-12-01',
    projects: [],
  };

  beforeEach(() => {
    mockCanUnlock = true;
    vi.mocked(accrualApi.lines.get).mockResolvedValue(EDIT_LINE as never);
    vi.mocked(accrualApi.lines.redistribute).mockResolvedValue({ cells_updated: 12 } as never);
  });

  it('hides the unlock checkbox without period_manage permission', async () => {
    mockCanUnlock = false;
    renderWith(<AccrualLineEditor lineId="l1" onClose={vi.fn()} />);
    await screen.findByText('Edit accrual line');
    expect(screen.queryByLabelText(/unlock frozen cells/i)).not.toBeInTheDocument();
  });

  it('redistribute sends include_frozen when unlock is checked', async () => {
    const user = userEvent.setup();
    renderWith(<AccrualLineEditor lineId="l1" onClose={vi.fn()} />);
    await screen.findByText('Edit accrual line');

    await user.click(screen.getByLabelText(/unlock frozen cells/i));
    await user.click(screen.getByRole('button', { name: /redistribute/i }));

    await waitFor(() =>
      expect(accrualApi.lines.redistribute).toHaveBeenCalledWith('l1', {
        force: true,
        includeFrozen: true,
      }),
    );
  });

  it('saves pending edits before redistributing (no manual save needed)', async () => {
    const user = userEvent.setup();
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l1' } as never);
    renderWith(<AccrualLineEditor lineId="l1" onClose={vi.fn()} />);
    await screen.findByText('Edit accrual line');

    const value = screen.getByLabelText('Value €');
    await user.clear(value);
    await user.type(value, '9999');

    // Button stays enabled while dirty; clicking it saves first, then redistributes.
    await user.click(screen.getByRole('button', { name: /redistribute/i }));

    // Edits are persisted (update) and only then redistributed — no manual save.
    await waitFor(() => expect(accrualApi.lines.update).toHaveBeenCalled());
    expect(accrualApi.lines.redistribute).toHaveBeenCalled();
  });

  it('shows a feedback message with the cell count after redistribute', async () => {
    const user = userEvent.setup();
    renderWith(<AccrualLineEditor lineId="l1" onClose={vi.fn()} />);
    await screen.findByText('Edit accrual line');

    await user.click(screen.getByRole('button', { name: /redistribute/i }));

    expect(await screen.findByRole('status')).toHaveTextContent(/redistributed across 12 cells/i);
  });
});
