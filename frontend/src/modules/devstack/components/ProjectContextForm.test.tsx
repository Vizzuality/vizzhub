import { describe, it, expect, vi, beforeEach } from 'vitest';
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

beforeEach(() => {
  createMutate.mockReset();
});

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

  it('prompts to associate when GitHub file already exists and resubmits with associate_existing', () => {
    const onClose = vi.fn();
    // First call: trigger 409 github_file_exists via onError.
    // Second call: succeed via onSuccess.
    createMutate
      .mockImplementationOnce((_payload, opts) => {
        opts.onError({
          response: {
            status: 409,
            data: {
              detail: {
                code: 'github_file_exists',
                slug: 'acme-corp',
                message: 'already there',
              },
            },
          },
        });
      })
      .mockImplementationOnce((_payload, opts) => {
        opts.onSuccess({
          id: 'ctx-1',
          slug: 'acme-corp',
          project_id: 'p1',
          project_name: 'Acme Corp',
          description: null,
          github_seeded: true,
          github_error: null,
        });
      });

    renderForm({ context: null, onClose });
    fireEvent.click(screen.getByRole('combobox', { name: /project/i }));
    fireEvent.click(screen.getByText('Acme Corp'));
    fireEvent.click(screen.getByRole('button', { name: /create/i }));

    // Confirmation dialog shows up.
    expect(
      screen.getByText(/GitHub file already exists/i),
    ).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /associate/i }));

    // Second mutate call carries associate_existing: true.
    expect(createMutate).toHaveBeenCalledTimes(2);
    expect(createMutate.mock.calls[1][0]).toMatchObject({
      slug: 'acme-corp',
      project_id: 'p1',
      associate_existing: true,
    });
    // And onSuccess fired → dialog closed.
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
