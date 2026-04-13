import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotesPanel } from '../NotesPanel';
import { isoDocNotesApi } from '../../services/notes';
import type { IsoDocNote } from '../../types/notes';

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

function makeNote(overrides: Partial<IsoDocNote> = {}): IsoDocNote {
  return {
    id: 'note-1',
    node_id: 'n1',
    content: 'Auditor flagged this',
    done: false,
    done_at: null,
    done_by_id: null,
    done_by_name: null,
    created_by_id: 'u1',
    created_by_name: 'Jane',
    created_at: '2026-04-13T00:00:00Z',
    updated_at: '2026-04-13T00:00:00Z',
    ...overrides,
  };
}

describe('NotesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state when no notes', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() =>
      expect(screen.getByText(/no notes yet/i)).toBeInTheDocument(),
    );
  });

  it('renders existing notes with author and content', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([
      makeNote({ content: 'First', created_by_name: 'Alice' }),
      makeNote({ id: 'note-2', content: 'Second', created_by_name: 'Bob' }),
    ]);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() => expect(screen.getByText('First')).toBeInTheDocument());
    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText(/notes \(2\)/i)).toBeInTheDocument();
  });

  it('clears the textarea after creating a note', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    vi.mocked(isoDocNotesApi.create).mockResolvedValue(makeNote({ content: 'hello' }));
    render(wrap(<NotesPanel nodeId="n1" />));
    const textarea = screen.getByPlaceholderText(/add a note/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'hello' } });
    fireEvent.click(screen.getByRole('button', { name: /add note/i }));
    await waitFor(() =>
      expect(isoDocNotesApi.create).toHaveBeenCalledWith('n1', { content: 'hello' }),
    );
    await waitFor(() => expect(textarea.value).toBe(''));
  });

  it('disables the Add button when draft is empty', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /add note/i })).toBeDisabled(),
    );
  });

  it('toggles a note to done when Mark done is clicked', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([makeNote()]);
    vi.mocked(isoDocNotesApi.update).mockResolvedValue(makeNote({ done: true }));
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() => expect(screen.getByText('Auditor flagged this')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /mark done/i }));
    await waitFor(() =>
      expect(isoDocNotesApi.update).toHaveBeenCalledWith('note-1', { done: true }),
    );
  });

  it('deletes a note after confirmation', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([makeNote()]);
    vi.mocked(isoDocNotesApi.remove).mockResolvedValue();
    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(true);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() => expect(screen.getByText('Auditor flagged this')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /delete note/i }));
    await waitFor(() => expect(isoDocNotesApi.remove).toHaveBeenCalledWith('note-1'));
    confirmSpy.mockRestore();
  });

  it('skips deletion if user cancels the confirm dialog', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([makeNote()]);
    vi.mocked(isoDocNotesApi.remove).mockResolvedValue();
    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() => expect(screen.getByText('Auditor flagged this')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /delete note/i }));
    expect(isoDocNotesApi.remove).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
