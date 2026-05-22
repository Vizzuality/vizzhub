import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LockedFxRateEditor } from '@/modules/accrual/components/LockedFxRateEditor';
import { projectsApi } from '@/core/services/projects';

vi.mock('@/core/services/projects', () => ({
  projectsApi: { update: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

function renderEditor(
  props: Partial<React.ComponentProps<typeof LockedFxRateEditor>> = {},
): { client: QueryClient } {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={client}>
      <LockedFxRateEditor
        projectId="p1"
        projectCurrency="USD"
        currentRate={null}
        canEdit
        {...props}
      />
    </QueryClientProvider>,
  );
  return { client };
}

describe('LockedFxRateEditor', () => {
  it('renders a plain span when canEdit is false', () => {
    renderEditor({ canEdit: false, currentRate: '1.10' });
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('1.10')).toBeInTheDocument();
  });

  it('opens a popover with the current rate when clicked', async () => {
    renderEditor({ currentRate: '1.234567' });
    await userEvent.click(screen.getByRole('button', { name: /set FX lock for USD/i }));
    const input = screen.getByRole('spinbutton');
    expect(input).toHaveValue(1.234567);
  });

  it('PATCHes the project on Save', async () => {
    (projectsApi.update as ReturnType<typeof vi.fn>).mockResolvedValue({});
    renderEditor({ currentRate: null });
    await userEvent.click(screen.getByRole('button', { name: /set FX lock for USD/i }));
    const input = screen.getByRole('spinbutton');
    await userEvent.type(input, '1.15');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => {
      expect(projectsApi.update).toHaveBeenCalledWith('p1', { locked_fx_rate: 1.15 });
    });
  });

  it('PATCHes with null on Clear', async () => {
    (projectsApi.update as ReturnType<typeof vi.fn>).mockResolvedValue({});
    renderEditor({ currentRate: '1.10' });
    await userEvent.click(screen.getByRole('button', { name: /set FX lock for USD/i }));
    await userEvent.click(screen.getByRole('button', { name: /clear/i }));
    await waitFor(() => {
      expect(projectsApi.update).toHaveBeenCalledWith('p1', { locked_fx_rate: null });
    });
  });

  it('disables Clear when there is no current rate', async () => {
    renderEditor({ currentRate: null });
    await userEvent.click(screen.getByRole('button', { name: /set FX lock for USD/i }));
    expect(screen.getByRole('button', { name: /clear/i })).toBeDisabled();
  });

  it('does not PATCH when the input is empty or non-positive', async () => {
    renderEditor({ currentRate: null });
    await userEvent.click(screen.getByRole('button', { name: /set FX lock for USD/i }));
    await userEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(projectsApi.update).not.toHaveBeenCalled();
  });
});
