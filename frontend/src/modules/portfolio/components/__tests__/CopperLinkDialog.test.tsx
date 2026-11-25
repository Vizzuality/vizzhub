import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CopperLinkDialog } from '../CopperLinkDialog';
import type { CopperLinkReport } from '../../types/portfolio';

const report: CopperLinkReport = {
  linked: 722,
  already_linked: 0,
  review: [
    {
      client_id: 'c-verra',
      client_name: 'Verra',
      reason: 'ambiguous_in_copper',
      candidates: [
        {
          id: 42412869,
          name: 'Verra',
          email_domain: 'verra.org',
          created_on: '2019-12-31',
          interaction_count: 39,
        },
        { id: 48274785, name: 'Verra', email_domain: null, created_on: '2020-08-10', interaction_count: 0 },
      ],
    },
    { client_id: 'c-sky', client_name: 'Sky Truth', reason: 'not_in_copper', candidates: [] },
  ],
};

const runLink = vi.fn().mockResolvedValue(report);
const updateClient = vi.fn().mockResolvedValue({});
vi.mock('../../hooks/useClients', () => ({
  useLinkClientsWithCopper: () => ({ mutateAsync: runLink, isPending: false, isError: false }),
  useUpdateClient: () => ({ mutateAsync: updateClient, isPending: false }),
}));

describe('CopperLinkDialog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('runs the linking and lists what needs review', async () => {
    render(<CopperLinkDialog open onOpenChange={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: /link now/i }));

    expect(
      await screen.findByText(
        (_, el) => el?.tagName === 'P' && /722 clients linked now/i.test(el.textContent ?? '')
      )
    ).toBeInTheDocument();
    expect(screen.getByText('Sky Truth')).toBeInTheDocument();
    expect(screen.getByText(/no copper company with this name/i)).toBeInTheDocument();
  });

  it('links an ambiguous client to the chosen Copper company', async () => {
    render(<CopperLinkDialog open onOpenChange={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /link now/i }));

    const row = (await screen.findByText('Verra', { selector: 'p' })).closest('li') as HTMLElement;
    await userEvent.click(within(row).getByLabelText(/verra\.org/i));
    await userEvent.click(within(row).getByRole('button', { name: /^link$/i }));

    await waitFor(() =>
      expect(updateClient).toHaveBeenCalledWith({
        id: 'c-verra',
        data: { copper_company_id: 42412869 },
      })
    );
    await waitFor(() => expect(screen.queryByText('Verra', { selector: 'p' })).not.toBeInTheDocument());
  });
});
