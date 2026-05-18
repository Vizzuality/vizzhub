import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '@/core/contexts/AuthContext';
import type { AuthContextType } from '@/core/types/auth';
import { Action } from '@/core/permissions';
import InvoiceDetailContent from '../InvoiceDetailContent';
import type { Invoice } from '../../types/tracker';

const mockCreate = vi.fn();
const mockTransition = vi.fn();
const mockDelete = vi.fn();

vi.mock('../../hooks/useInvoices', () => ({
  useCreateInvoice: () => ({ mutate: mockCreate, isPending: false }),
  useTransitionInvoice: () => ({ mutate: mockTransition, isPending: false }),
  useDeleteInvoice: () => ({ mutate: mockDelete, isPending: false }),
  useUpdateInvoice: () => ({ mutate: vi.fn(), isPending: false }),
}));

const mockListPostponements = vi.fn().mockResolvedValue([]);
const mockApprove = vi.fn();
const mockReject = vi.fn();
const mockCancel = vi.fn();

vi.mock('../../services/tracker', () => ({
  trackerApi: {
    listPostponements: (...args: unknown[]) => mockListPostponements(...args),
    postponeInvoice: vi.fn(),
    deleteLatestPostponement: vi.fn(),
    approvePostponement: (...args: unknown[]) => mockApprove(...args),
    rejectPostponement: (...args: unknown[]) => mockReject(...args),
    cancelPostponement: (...args: unknown[]) => mockCancel(...args),
  },
}));

function renderWithProviders(
  ui: React.ReactElement,
  permissions: string[] = [Action.TRACKER_MANAGE],
): ReturnType<typeof render> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{
          user: null,
          isAuthenticated: true,
          isLoading: false,
          permissions,
          roles: ['manager'],
          login: vi.fn(),
          logout: vi.fn(),
          refresh: vi.fn(),
        } as unknown as AuthContextType}
      >
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const baseInvoice: Invoice = {
  id: 'inv-1',
  project_id: 'proj-1',
  code: 'INV-001',
  amount: 5000,
  due_date: '2026-06-01',
  invoiced_on: null,
  milestone: 'Phase 1',
  observations: null,
  invoicing_contact_name: null,
  invoicing_contact_email: null,
  status: 'pending_to_issue',
  postpone_count: 0,
  postponed_to: null,
};

describe('InvoiceDetailContent — edit mode', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows pending_to_issue status with explanation and both contextual actions', () => {
    renderWithProviders(
      <InvoiceDetailContent invoice={baseInvoice} projectId="proj-1" currency="euro" />,
    );
    expect(screen.getByText('Pending to invoice')).toBeInTheDocument();
    expect(screen.getByText(/Ready to send to the client/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Mark as invoiced/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Request postpone/ })).toBeInTheDocument();
    // Should NOT show "Mark as paid" (only valid from waiting_for_payment)
    expect(screen.queryByRole('button', { name: /Mark as paid/ })).not.toBeInTheDocument();
  });

  it('shows Postpone and Issue-now for scheduled invoices (future due_date)', () => {
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{ ...baseInvoice, status: 'scheduled', due_date: '2030-01-01' }}
        projectId="proj-1"
        currency="euro"
      />,
    );
    expect(screen.getByText('Scheduled')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Request postpone/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Issue now/ })).toBeInTheDocument();
    // No primary "Mark as invoiced" — early issue uses the warning Issue-now flow
    expect(screen.queryByRole('button', { name: /Mark as invoiced/ })).not.toBeInTheDocument();
  });

  it('shows waiting_for_payment status with mark-paid and revert actions', () => {
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{ ...baseInvoice, status: 'waiting_for_payment', invoiced_on: '2026-04-01' }}
        projectId="proj-1"
        currency="euro"
      />,
    );
    expect(screen.getByText('Waiting for payment')).toBeInTheDocument();
    expect(screen.getByText(/Sent on 2026-04-01/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Mark as paid/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Revert to pending/ })).toBeInTheDocument();
  });

  it('shows paid status with revert-to-waiting action only', () => {
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{ ...baseInvoice, status: 'paid', invoiced_on: '2026-04-01' }}
        projectId="proj-1"
        currency="euro"
      />,
    );
    expect(screen.getByText('Paid')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Revert to waiting/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mark as paid/ })).not.toBeInTheDocument();
  });

  it('shows postponed banner with re-open instruction', () => {
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{
          ...baseInvoice,
          status: 'postponed',
          postponed_to: '2026-07-01',
          postpone_count: 1,
        }}
        projectId="proj-1"
        currency="euro"
      />,
    );
    expect(screen.getByText('Postponed')).toBeInTheDocument();
    expect(screen.getByText(/Postponed to 2026-07-01/)).toBeInTheDocument();
    // No transitions allowed from postponed
    expect(screen.queryByRole('button', { name: /Mark as/ })).not.toBeInTheDocument();
  });

  it('renders pending request banner with Approve / Reject for admin', async () => {
    mockListPostponements.mockResolvedValueOnce([
      {
        id: 'pp-1',
        invoice_id: 'inv-1',
        postponed_to: '2026-08-01',
        reason: 'client asked',
        created_by: 'user-X',
        created_by_name: 'Maria',
        created_at: '2026-05-10T10:00:00Z',
        approval_status: 'pending',
        decided_by: null,
        decided_by_name: null,
        decided_at: null,
        decision_note: null,
      },
    ]);
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{ ...baseInvoice, status: 'postpone_pending' }}
        projectId="proj-1"
        currency="euro"
      />,
      ['*'],
    );
    expect(await screen.findByText('Awaiting approval')).toBeInTheDocument();
    expect(await screen.findByText('Maria')).toBeInTheDocument();
    expect(await screen.findByText(/client asked/)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Approve/ })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Reject/ })).toBeInTheDocument();
  });

  it('non-admin without TRACKER_MANAGE sees neither approve nor cancel', async () => {
    mockListPostponements.mockResolvedValueOnce([
      {
        id: 'pp-1',
        invoice_id: 'inv-1',
        postponed_to: '2026-08-01',
        reason: 'r',
        created_by: 'user-X',
        created_by_name: 'Maria',
        created_at: '2026-05-10T10:00:00Z',
        approval_status: 'pending',
        decided_by: null,
        decided_by_name: null,
        decided_at: null,
        decision_note: null,
      },
    ]);
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{ ...baseInvoice, status: 'postpone_pending' }}
        projectId="proj-1"
        currency="euro"
      />,
      [],
    );
    expect(await screen.findByText('Awaiting approval')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reject/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Cancel request/ })).not.toBeInTheDocument();
  });

  it('renders Delete action when user has TRACKER_MANAGE', () => {
    renderWithProviders(
      <InvoiceDetailContent invoice={baseInvoice} projectId="proj-1" currency="euro" />,
    );
    expect(screen.getByRole('button', { name: /Delete/ })).toBeInTheDocument();
  });

  it('hides all write affordances without TRACKER_MANAGE', () => {
    renderWithProviders(
      <InvoiceDetailContent invoice={baseInvoice} projectId="proj-1" currency="euro" />,
      [],
    );
    expect(screen.queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mark as invoiced/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Postpone/ })).not.toBeInTheDocument();
  });

  it('renders invoicing contact fields when present', () => {
    renderWithProviders(
      <InvoiceDetailContent
        invoice={{
          ...baseInvoice,
          invoicing_contact_name: 'Maria Lopez',
          invoicing_contact_email: 'maria@client.com',
        }}
        projectId="proj-1"
        currency="euro"
      />,
    );
    expect(screen.getByText('Maria Lopez')).toBeInTheDocument();
    expect(screen.getByText('maria@client.com')).toBeInTheDocument();
  });
});

describe('InvoiceDetailContent — create mode', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders form with required fields and currency hint', () => {
    renderWithProviders(
      <InvoiceDetailContent projectId="proj-1" currency="usd" />,
    );
    expect(screen.getByText('New invoice')).toBeInTheDocument();
    expect(screen.getByText('USD')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create invoice/ })).toBeInTheDocument();
  });

  it('submits when required fields are filled', () => {
    renderWithProviders(
      <InvoiceDetailContent projectId="proj-1" currency="euro" onClose={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText('Milestone'), { target: { value: 'Test M' } });
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '1500' } });
    fireEvent.change(screen.getByLabelText('Due date'), { target: { value: '2026-08-01' } });

    fireEvent.click(screen.getByRole('button', { name: /Create invoice/ }));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ milestone: 'Test M', amount: 1500, due_date: '2026-08-01' }),
      expect.any(Object),
    );
  });

  it('blocks submit when required fields are empty', () => {
    renderWithProviders(<InvoiceDetailContent projectId="proj-1" currency="euro" />);
    fireEvent.click(screen.getByRole('button', { name: /Create invoice/ }));
    expect(mockCreate).not.toHaveBeenCalled();
    expect(screen.getByText(/required/i)).toBeInTheDocument();
  });
});
