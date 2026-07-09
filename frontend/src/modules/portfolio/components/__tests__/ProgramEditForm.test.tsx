import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ProgramEditForm } from '../ProgramEditForm';

const rename = vi.fn().mockResolvedValue({});
const updateProfile = vi.fn().mockResolvedValue({});
const replaceTerms = vi.fn().mockResolvedValue([]);

vi.mock('../../hooks/usePrograms', () => ({
  useRenameProgram: () => ({ mutateAsync: rename, isPending: false }),
  useUpdateProgramProfile: () => ({ mutateAsync: updateProfile, isPending: false }),
  useReplaceProgramTerms: () => ({ mutateAsync: replaceTerms, isPending: false }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({
    data: [
      {
        id: 'tax-single', slug: 'client-type', name: 'Client Type', description: null,
        cardinality: 'single', allows_primary: false, is_active: true, sort_order: 0,
        terms: [
          { id: 'ngo', taxonomy_id: 'tax-single', slug: 'ngo', name: 'NGO', description: null, sort_order: 0, is_active: true },
          { id: 'gov', taxonomy_id: 'tax-single', slug: 'government', name: 'Government', description: null, sort_order: 1, is_active: true },
        ],
      },
      {
        id: 'tax-svc', slug: 'service', name: 'Service', description: null,
        cardinality: 'multi', allows_primary: true, is_active: true, sort_order: 1,
        terms: [
          { id: 'tools', taxonomy_id: 'tax-svc', slug: 'tools', name: 'Tools', description: null, sort_order: 0, is_active: true },
          { id: 'sci', taxonomy_id: 'tax-svc', slug: 'sci', name: 'Scientific', description: null, sort_order: 1, is_active: true },
        ],
      },
    ],
    isLoading: false,
  }),
}));

const PROGRAM = {
  id: 'p1',
  name: 'Alpha',
  profile: {
    objective: 'Old objective', short_description: null, web_copy: null,
    website_url: null, impact_story: null, main_partner: null, stage: 'live', on_website: false,
  },
  clients: [],
  projects: [],
  terms: [
    { term_id: 'ngo', taxonomy_id: 'tax-single', taxonomy_slug: 'client-type', name: 'NGO', is_primary: false },
    { term_id: 'tools', taxonomy_id: 'tax-svc', taxonomy_slug: 'service', name: 'Tools', is_primary: false },
  ],
};

const onDone = vi.fn();

function renderForm(): void {
  render(<ProgramEditForm program={PROGRAM} onDone={onDone} />);
}

async function save(): Promise<void> {
  fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
  await waitFor(() => expect(onDone).toHaveBeenCalled());
}

describe('ProgramEditForm', () => {
  beforeEach(() => {
    rename.mockClear();
    updateProfile.mockClear();
    replaceTerms.mockClear();
    onDone.mockClear();
  });

  it('saves only the changed profile fields as a diff', async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText('Website'), {
      target: { value: 'https://example.org' },
    });
    await save();
    expect(updateProfile).toHaveBeenCalledWith({ website_url: 'https://example.org' });
    expect(rename).not.toHaveBeenCalled();
    expect(replaceTerms).not.toHaveBeenCalled();
  });

  it('prefixes https:// on bare-domain website values', async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText('Website'), { target: { value: 'example.org' } });
    await save();
    expect(updateProfile).toHaveBeenCalledWith({ website_url: 'https://example.org' });
  });

  it('renames when the name changes', async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Beta' } });
    await save();
    expect(rename).toHaveBeenCalledWith('Beta');
    expect(updateProfile).not.toHaveBeenCalled();
  });

  it('single cardinality: picking a second term replaces the first', async () => {
    renderForm();
    fireEvent.click(screen.getByRole('button', { name: 'Government' }));
    await save();
    expect(replaceTerms).toHaveBeenCalledTimes(1);
    expect(replaceTerms).toHaveBeenCalledWith({
      taxonomy_id: 'tax-single',
      term_ids: ['gov'],
      primary_term_id: null,
    });
  });

  it('allows_primary: second click promotes to primary, third deselects', async () => {
    renderForm();
    const tools = screen.getByRole('button', { name: /tools/i });
    fireEvent.click(tools); // already selected → promote to primary
    await save();
    expect(replaceTerms).toHaveBeenCalledWith({
      taxonomy_id: 'tax-svc',
      term_ids: ['tools'],
      primary_term_id: 'tools',
    });

    onDone.mockClear();
    replaceTerms.mockClear();
  });

  it('deselects a primary term on the third click', async () => {
    renderForm();
    const tools = screen.getByRole('button', { name: /tools/i });
    fireEvent.click(tools); // → primary
    fireEvent.click(tools); // → deselected
    await save();
    expect(replaceTerms).toHaveBeenCalledWith({
      taxonomy_id: 'tax-svc',
      term_ids: [],
      primary_term_id: null,
    });
  });

  it('does not call any mutation when nothing changed', async () => {
    renderForm();
    await save();
    expect(rename).not.toHaveBeenCalled();
    expect(updateProfile).not.toHaveBeenCalled();
    expect(replaceTerms).not.toHaveBeenCalled();
  });
});
