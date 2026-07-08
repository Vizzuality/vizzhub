import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ProjectCard from '../ProjectCard';
import type { Project } from '@/core/types/project';

const project: Project = {
  id: 'p1',
  name: 'Ocean Watch',
  code: 'OCW',
  program_id: null,
  program_name: null,
  is_billable: true,
  has_scorecard: true,
  has_dependabot_alerts: false,
  has_budget_alerts: false,
  currency: 'EUR',
  budget: 1000,
  notes: null,
  summary: null,
  jira_project_key: null,
  github_repo: null,
  slack_channel_id: null,
  project_manager_id: null,
  project_manager_name: null,
  client_id: null,
  client_name: null,
  start_date: null,
  end_date: null,
  status: 'live',
  finished_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function renderCard(props: Partial<Parameters<typeof ProjectCard>[0]> = {}): void {
  render(
    <MemoryRouter>
      <ProjectCard project={project} {...props} />
    </MemoryRouter>,
  );
}

describe('ProjectCard', () => {
  it.each(['list', 'grid'] as const)(
    'links the whole %s card to the project hub',
    (viewMode) => {
      renderCard({ viewMode });
      expect(screen.getByRole('link', { name: 'Ocean Watch' })).toHaveAttribute(
        'href',
        '/projects/p1',
      );
    },
  );

  it('has no Tracker or Scorecard links', () => {
    renderCard({ isAdmin: true });
    expect(screen.queryByRole('link', { name: /tracker/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /scorecard/i })).not.toBeInTheDocument();
  });

  it.each(['list', 'grid'] as const)(
    'shows the edit icon link for admins in %s view',
    (viewMode) => {
      renderCard({ viewMode, isAdmin: true });
      expect(screen.getByRole('link', { name: 'Edit Ocean Watch' })).toHaveAttribute(
        'href',
        '/projects/p1/edit',
      );
    },
  );

  it('hides the edit link for non-admins', () => {
    renderCard({ isAdmin: false });
    expect(screen.queryByRole('link', { name: 'Edit Ocean Watch' })).not.toBeInTheDocument();
  });
});
