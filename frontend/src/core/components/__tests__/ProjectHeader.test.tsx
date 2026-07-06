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
});
