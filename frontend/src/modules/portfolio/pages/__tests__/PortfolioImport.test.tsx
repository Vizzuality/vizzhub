import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { OverviewMatch } from '../../types/portfolio';
import PortfolioImport from '../PortfolioImport';

const mockPermission = vi.fn();
vi.mock('@/core/permissions/usePermission', () => ({ usePermission: () => mockPermission() }));

const mockCurrent = vi.fn();
const mockMatches = vi.fn();
vi.mock('../../hooks/useOverviewImport', () => ({
  useCurrentImportBatch: () => mockCurrent(),
  useOverviewMatches: () => mockMatches(),
  useUploadOverview: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApplyOverview: () => ({ mutate: vi.fn(), isPending: false, data: undefined }),
  useSaveDecision: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useImportProjects: () => ({ data: [] }),
}));
vi.mock('@/core/hooks/usePrograms', () => ({ usePrograms: () => ({ data: [] }) }));

function renderPage(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PortfolioImport />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MATCH: OverviewMatch = {
  staging_id: 's1',
  name: 'Example row',
  is_old_project: false,
  client_type_raw: null,
  service_raw: null,
  impact_area_raw: null,
  suggested_project: { project_id: null, score: 0 },
  project_candidates: [],
  current_program: { program_id: null, name: null },
  program_candidates: [],
  suggested_program: { program_id: null, score: 0 },
  saved_decision: { project_id: null, program_action: 'create', program_id: null, new_program_name: 'Example row' },
};

describe('PortfolioImport', () => {
  it('shows the upload dropzone for a manager', () => {
    mockPermission.mockReturnValue(true);
    mockCurrent.mockReturnValue({ data: null });
    mockMatches.mockReturnValue({ data: undefined, isLoading: false });
    renderPage();
    expect(screen.getByLabelText('Overview spreadsheet')).toBeInTheDocument();
  });

  it('redirects a non-manager away', () => {
    mockPermission.mockReturnValue(false);
    mockCurrent.mockReturnValue({ data: null });
    mockMatches.mockReturnValue({ data: undefined, isLoading: false });
    renderPage();
    expect(screen.queryByLabelText('Overview spreadsheet')).not.toBeInTheDocument();
  });

  it('reveals the upload dropzone after Start over discards a resumed batch', async () => {
    const user = userEvent.setup();
    mockPermission.mockReturnValue(true);
    mockCurrent.mockReturnValue({ data: { batch_id: 'b1', row_count: 1 } });
    mockMatches.mockReturnValue({ data: [MATCH], isLoading: false });
    renderPage();

    // The resumed batch renders its review list, not the dropzone.
    expect(await screen.findByText('Example row')).toBeInTheDocument();
    expect(screen.queryByLabelText('Overview spreadsheet')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Start over' }));
    await user.click(screen.getByRole('button', { name: 'Discard & upload new' }));

    // Even though useCurrentImportBatch still returns the batch, Start over must
    // suppress auto-resume so the dropzone becomes reachable.
    expect(await screen.findByLabelText('Overview spreadsheet')).toBeInTheDocument();
  });
});
