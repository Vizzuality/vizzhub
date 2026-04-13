import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotesPanel } from '../NotesPanel';
import { isoDocNotesApi } from '../../services/notes';

vi.mock('../../services/notes');

vi.mock('@/shared/components/doc/DocViewer', () => ({
  DocViewer: ({ content }: { content: string }) => <div>{content}</div>,
}));

function wrap(ui: React.ReactNode): JSX.Element {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe('NotesPanel', () => {
  it('renders empty state when no notes', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() =>
      expect(screen.getByText(/no notes yet/i)).toBeInTheDocument(),
    );
  });

  it('creates a note when typing and clicking Add', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    vi.mocked(isoDocNotesApi.create).mockResolvedValue({
      id: 'x',
      node_id: 'n1',
      content: 'hello',
      done: false,
      done_at: null,
      done_by_id: null,
      done_by_name: null,
      created_by_id: 'u1',
      created_by_name: 'Test',
      created_at: '2026-04-13T00:00:00Z',
      updated_at: '2026-04-13T00:00:00Z',
    });
    render(wrap(<NotesPanel nodeId="n1" />));
    fireEvent.change(screen.getByPlaceholderText(/add a note/i), {
      target: { value: 'hello' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add note/i }));
    await waitFor(() =>
      expect(isoDocNotesApi.create).toHaveBeenCalledWith('n1', { content: 'hello' }),
    );
  });
});
