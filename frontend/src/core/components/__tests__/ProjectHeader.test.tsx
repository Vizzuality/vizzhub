import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import { ProjectHeader } from '../ProjectHeader';
import type { Project } from '@/core/types/project';

vi.mock('@/core/permissions', () => ({
  usePermission: () => true,
  Action: { PROJECTS_MANAGE: 'projects:manage' },
}));

const project = {
  id: 'p1', name: 'Ocean Watch', code: 'VIZZ.OCW.25', status: 'live',
  start_date: '2024-01-01', end_date: '2026-01-01', program_name: 'Blue Programs',
} as Project;

describe('ProjectHeader', () => {
  it('renders identity with a status dot (no badge)', () => {
    render(
      <MemoryRouter>
        <ProjectProvider project={project}><ProjectHeader /></ProjectProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText('Ocean Watch')).toBeInTheDocument();
    expect(screen.getByText('VIZZ.OCW.25')).toBeInTheDocument();
    expect(screen.getByText('Blue Programs')).toBeInTheDocument();
  });
});
