import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ProjectContexts from './ProjectContexts';

vi.mock('@/core/permissions', () => ({
  usePermission: vi.fn(() => true),
  Action: { DEVSTACK_MANAGE: 'devstack:manage' },
}));

vi.mock('../hooks/useProjectContexts', () => ({
  useProjectContexts: () => ({
    data: [
      {
        id: '1',
        slug: 'acme-corp',
        project_id: 'p1',
        project_name: 'Acme Corp',
        description: 'Notes',
      },
    ],
    isLoading: false,
  }),
  useDeleteProjectContext: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProjectContexts />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProjectContexts page', () => {
  it('renders list of contexts', () => {
    renderPage();
    expect(screen.getByText('acme-corp')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  it('shows New button when user has DEVSTACK_MANAGE', () => {
    renderPage();
    expect(
      screen.getByRole('button', { name: /new project context/i }),
    ).toBeInTheDocument();
  });
});
