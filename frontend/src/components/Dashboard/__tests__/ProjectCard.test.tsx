import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ProjectCard from '../ProjectCard';
import type { Project } from '../../../types';

function renderWithRouter(component: React.ReactElement) {
  return render(<BrowserRouter>{component}</BrowserRouter>);
}

describe('ProjectCard', () => {
  const mockProject: Project = {
    id: 'project-123',
    name: 'Test Project',
    jira_project_key: 'TEST',
    github_repo: 'org/test-repo',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-15T00:00:00Z',
  };

  it('renders project name', () => {
    renderWithRouter(<ProjectCard project={mockProject} />);

    expect(screen.getByText('Test Project')).toBeDefined();
  });

  it('renders Jira project key when provided', () => {
    renderWithRouter(<ProjectCard project={mockProject} />);

    expect(screen.getByText(/Jira: TEST/)).toBeDefined();
  });

  it('renders GitHub repo when provided', () => {
    renderWithRouter(<ProjectCard project={mockProject} />);

    expect(screen.getByText(/GitHub: org\/test-repo/)).toBeDefined();
  });

  it('does not render Jira key when not provided', () => {
    const projectWithoutJira: Project = {
      ...mockProject,
      jira_project_key: null,
    };

    renderWithRouter(<ProjectCard project={projectWithoutJira} />);

    expect(screen.queryByText('TEST')).toBeNull();
  });

  it('does not render GitHub repo when not provided', () => {
    const projectWithoutGithub: Project = {
      ...mockProject,
      github_repo: null,
    };

    renderWithRouter(<ProjectCard project={projectWithoutGithub} />);

    expect(screen.queryByText('org/test-repo')).toBeNull();
  });

  it('renders start and end dates when both provided', () => {
    const projectWithDates: Project = {
      ...mockProject,
      start_date: '2026-01-01',
      end_date: '2026-03-31',
    };

    renderWithRouter(<ProjectCard project={projectWithDates} />);

    const dateText = screen.getByText(/Jan 1, 2026 - Mar 31, 2026/);
    expect(dateText).toBeDefined();
  });

  it('renders only start date when end date not provided', () => {
    const projectWithStartDate: Project = {
      ...mockProject,
      start_date: '2026-01-01',
      end_date: null,
    };

    renderWithRouter(<ProjectCard project={projectWithStartDate} />);

    const dateText = screen.getByText(/Jan 1, 2026/);
    expect(dateText).toBeDefined();
  });

  it('renders only end date when start date not provided', () => {
    const projectWithEndDate: Project = {
      ...mockProject,
      start_date: null,
      end_date: '2026-03-31',
    };

    renderWithRouter(<ProjectCard project={projectWithEndDate} />);

    const dateText = screen.getByText(/Mar 31, 2026/);
    expect(dateText).toBeDefined();
  });

  it('links to project detail page', () => {
    renderWithRouter(<ProjectCard project={mockProject} />);

    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe('/projects/project-123');
  });

  it('renders minimal project with only name', () => {
    const minimalProject: Project = {
      id: 'project-456',
      name: 'Minimal Project',
      jira_project_key: null,
      github_repo: null,
      start_date: null,
      end_date: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };

    renderWithRouter(<ProjectCard project={minimalProject} />);

    expect(screen.getByText('Minimal Project')).toBeDefined();
  });
});
