import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import { ProjectHeader } from '../ProjectHeader';
import type { Project } from '@/core/types/project';

let mockPerms: Record<string, boolean> = {};
vi.mock('@/core/permissions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/core/permissions')>();
  return {
    ...actual,
    usePermission: (action: string) => mockPerms[action] ?? false,
  };
});

vi.mock('@/modules/scorecard/hooks/useProjectScoresMap', () => ({
  useProjectScoresMap: () => ({ scoresMap: { p1: 82 } }),
}));

vi.mock('@/modules/tracker/public', () => ({
  useProjectCostsMap: () => ({ costsMap: { p1: { burn_percentage: 45.2 } } }),
  useProjectProgressMap: () => ({ progressMap: { p1: { percentage: 60 } } }),
}));

const project = {
  id: 'p1', name: 'Ocean Watch', code: 'VIZZ.OCW.25', status: 'live',
  start_date: '2024-01-01', end_date: '2026-01-01', program_name: 'Blue Programs',
} as Project;

function renderHeader(overrides: Partial<Project> = {}) {
  const p = { ...project, ...overrides } as Project;
  render(
    <MemoryRouter>
      <ProjectProvider project={p}><ProjectHeader /></ProjectProvider>
    </MemoryRouter>,
  );
}

describe('ProjectHeader', () => {
  it('renders identity with a status dot (no badge)', () => {
    mockPerms = { 'projects:manage': true };
    renderHeader();
    expect(screen.getByText('Ocean Watch')).toBeInTheDocument();
    expect(screen.getByText('VIZZ.OCW.25')).toBeInTheDocument();
    expect(screen.getByText('Blue Programs')).toBeInTheDocument();
  });

  it('links the program chip to the program page with portfolio permission', () => {
    mockPerms = { 'portfolio:view': true };
    renderHeader({ program_id: 'prog-1', program_name: 'Alpha Program' });
    const link = screen.getByRole('link', { name: /Alpha Program/ });
    expect(link).toHaveAttribute('href', '/admin/portfolio/programs/prog-1');
  });

  it('renders the program chip as plain text without portfolio permission', () => {
    mockPerms = {};
    renderHeader({ program_id: 'prog-1', program_name: 'Alpha Program' });
    expect(screen.getByText('Alpha Program')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Alpha Program/ })).not.toBeInTheDocument();
  });

  it('shows the project manager in the meta row', () => {
    mockPerms = {};
    renderHeader({ project_manager_name: 'Jane Doe' });
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
  });

  it('shows Score, Burn and Progress KPIs with scorecard + tracker access', () => {
    mockPerms = { 'tracker:view': true };
    renderHeader({ has_scorecard: true });
    expect(screen.getByText('Score')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('Burn')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getByText('Progress')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();
  });

  it('hides tracker KPIs without tracker permission', () => {
    mockPerms = {};
    renderHeader({ has_scorecard: true });
    expect(screen.getByText('Score')).toBeInTheDocument();
    expect(screen.queryByText('Burn')).not.toBeInTheDocument();
    expect(screen.queryByText('Progress')).not.toBeInTheDocument();
  });
});
