import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectContextForm } from './ProjectContextForm';

vi.mock('@/core/hooks/useProjects', () => ({
  useActiveProjectSummaries: () => ({
    data: [{ id: 'p1', name: 'Acme Corp' }],
  }),
}));

const createMutate = vi.fn();
vi.mock('../hooks/useProjectContexts', () => ({
  useCreateProjectContext: () => ({ mutate: createMutate, isPending: false }),
  useUpdateProjectContext: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderForm(props: Parameters<typeof ProjectContextForm>[0]) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <ProjectContextForm {...props} />
    </QueryClientProvider>,
  );
}

describe('ProjectContextForm', () => {
  it('auto-slugs from project name', () => {
    renderForm({ context: null, onClose: vi.fn() });
    fireEvent.click(screen.getByRole('combobox', { name: /project/i }));
    fireEvent.click(screen.getByText('Acme Corp'));
    const slugInput = screen.getByLabelText(/slug/i) as HTMLInputElement;
    expect(slugInput.value).toBe('acme-corp');
  });

  it('disables slug and project in edit mode', () => {
    renderForm({
      context: {
        id: '1',
        slug: 'existing',
        project_id: 'p1',
        project_name: 'Acme Corp',
        description: null,
      },
      onClose: vi.fn(),
    });
    expect(screen.getByLabelText(/slug/i)).toBeDisabled();
    expect(screen.getByRole('combobox', { name: /project/i })).toBeDisabled();
  });

  it('rejects invalid slug shape', () => {
    renderForm({ context: null, onClose: vi.fn() });
    // Select a project first so the Create button is enabled
    fireEvent.click(screen.getByRole('combobox', { name: /project/i }));
    fireEvent.click(screen.getByText('Acme Corp'));
    // Override auto-slug with an invalid value
    const slugInput = screen.getByLabelText(/slug/i);
    fireEvent.change(slugInput, { target: { value: 'Invalid Slug' } });
    fireEvent.click(screen.getByRole('button', { name: /create/i }));
    expect(screen.getByText(/lowercase letters, digits, hyphens/i)).toBeInTheDocument();
    expect(createMutate).not.toHaveBeenCalled();
  });
});
