import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProjectCard from '../ProjectCard';
import type { Project } from '@/core/types/project';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithRouter(component: React.ReactElement): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{component}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('ProjectCard', () => {
  const mockProject: Project = {
    id: 'project-123',
    name: 'Test Project',
    jira_project_key: 'TEST',
    github_repo: 'org/test-repo',
    status: 'live',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-15T00:00:00Z',
  };

  describe('List View (default)', () => {
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
      expect(link.getAttribute('href')).toBe('/projects/project-123/scorecard');
    });

    it('renders minimal project with only name', () => {
      const minimalProject: Project = {
        id: 'project-456',
        name: 'Minimal Project',
        jira_project_key: null,
        github_repo: null,
        start_date: null,
        end_date: null,
        status: 'live',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      renderWithRouter(<ProjectCard project={minimalProject} />);

      expect(screen.getByText('Minimal Project')).toBeDefined();
    });

    it('renders View Details link in list view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="list" />);

      expect(screen.getByText('View Details →')).toBeDefined();
    });

    it('renders Live badge for live status', () => {
      renderWithRouter(<ProjectCard project={mockProject} />);

      expect(screen.getByText('Live')).toBeDefined();
    });

    it('renders Finished badge for finished status', () => {
      const finishedProject: Project = {
        ...mockProject,
        status: 'finished',
      };

      renderWithRouter(<ProjectCard project={finishedProject} />);

      expect(screen.getByText('Finished')).toBeDefined();
    });
  });

  describe('Grid View', () => {
    it('renders project name in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.getByText('Test Project')).toBeDefined();
    });

    it('renders Jira key without prefix in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.getByText('TEST')).toBeDefined();
    });

    it('renders GitHub repo without prefix in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.getByText('org/test-repo')).toBeDefined();
    });

    it('does not render View Details link in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.queryByText('View Details →')).toBeNull();
    });

    it('entire card is clickable link in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      const link = screen.getByRole('link');
      expect(link.getAttribute('href')).toBe('/projects/project-123/scorecard');
    });

    it('renders dates in grid view', () => {
      const projectWithDates: Project = {
        ...mockProject,
        start_date: '2026-01-01',
        end_date: '2026-06-30',
      };

      renderWithRouter(<ProjectCard project={projectWithDates} viewMode="grid" />);

      expect(screen.getByText(/Jan 1, 2026 - Jun 30, 2026/)).toBeDefined();
    });

    it('renders Live badge in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.getByText('Live')).toBeDefined();
    });

    it('renders Finished badge in grid view', () => {
      const finishedProject: Project = {
        ...mockProject,
        status: 'finished',
      };

      renderWithRouter(<ProjectCard project={finishedProject} viewMode="grid" />);

      expect(screen.getByText('Finished')).toBeDefined();
    });

    it('does not show dates section when no dates provided', () => {
      const projectNoDates: Project = {
        ...mockProject,
        start_date: null,
        end_date: null,
      };

      renderWithRouter(<ProjectCard project={projectNoDates} viewMode="grid" />);

      const calendarIcons = document.querySelectorAll('[class*="Calendar"]');
      expect(calendarIcons.length).toBe(0);
    });
  });

  describe('Score Badge', () => {
    it('renders dash when score is null', () => {
      renderWithRouter(<ProjectCard project={mockProject} score={null} />);

      const scoreElements = screen.getAllByText(/Score:/);
      expect(scoreElements.length).toBeGreaterThan(0);
      expect(screen.getByText('—')).toBeDefined();
    });

    it('renders dash when score is undefined', () => {
      renderWithRouter(<ProjectCard project={mockProject} score={undefined} />);

      expect(screen.getByText('—')).toBeDefined();
    });

    it('renders score value when provided', () => {
      renderWithRouter(<ProjectCard project={mockProject} score={85} />);

      expect(screen.getByText('85')).toBeDefined();
    });

    it('rounds score to nearest integer', () => {
      renderWithRouter(<ProjectCard project={mockProject} score={85.7} />);

      expect(screen.getByText('86')).toBeDefined();
    });

    it('displays green dot for high scores (>=80)', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={85} />);

      const dotElement = container.querySelector('.bg-aux-neon-grass');
      expect(dotElement).toBeDefined();
    });

    it('displays yellow dot for medium scores (60-79)', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={70} />);

      const dotElement = container.querySelector('.bg-aux-yellow');
      expect(dotElement).toBeDefined();
    });

    it('displays red dot for low scores (<60)', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={45} />);

      const dotElement = container.querySelector('.bg-aux-red');
      expect(dotElement).toBeDefined();
    });

    it('renders score badge in grid view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" score={92} />);

      expect(screen.getByText('92')).toBeDefined();
    });

    it('renders score badge in list view', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="list" score={75} />);

      expect(screen.getByText('75')).toBeDefined();
    });

    it('handles edge case score of exactly 80', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={80} />);

      expect(screen.getByText('80')).toBeDefined();
      const greenDot = container.querySelector('.bg-aux-neon-grass');
      expect(greenDot).toBeDefined();
    });

    it('handles edge case score of exactly 60', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={60} />);

      expect(screen.getByText('60')).toBeDefined();
      const yellowDot = container.querySelector('.bg-aux-yellow');
      expect(yellowDot).toBeDefined();
    });

    it('handles score of 0', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={0} />);

      expect(screen.getByText('0')).toBeDefined();
      const redDot = container.querySelector('.bg-aux-red');
      expect(redDot).toBeDefined();
    });

    it('handles score of 100', () => {
      const { container } = renderWithRouter(<ProjectCard project={mockProject} score={100} />);

      expect(screen.getByText('100')).toBeDefined();
      const greenDot = container.querySelector('.bg-aux-neon-grass');
      expect(greenDot).toBeDefined();
    });
  });

  describe('Props', () => {
    it('defaults to list viewMode when not specified', () => {
      renderWithRouter(<ProjectCard project={mockProject} />);

      expect(screen.getByText('View Details →')).toBeDefined();
    });

    it('accepts explicit list viewMode', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="list" />);

      expect(screen.getByText('View Details →')).toBeDefined();
    });

    it('accepts grid viewMode', () => {
      renderWithRouter(<ProjectCard project={mockProject} viewMode="grid" />);

      expect(screen.queryByText('View Details →')).toBeNull();
    });
  });

  describe('Stale metrics warning (audit #17)', () => {
    function currentPeriod(): string {
      const now = new Date();
      const y = now.getUTCFullYear();
      const m = String(now.getUTCMonth() + 1).padStart(2, '0');
      return `${y}-${m}`;
    }

    function oldPeriod(): string {
      // 6 months ago — well above the 35-day threshold
      const now = new Date();
      const ref = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 6, 1));
      const y = ref.getUTCFullYear();
      const m = String(ref.getUTCMonth() + 1).padStart(2, '0');
      return `${y}-${m}`;
    }

    it('shows warning for LIVE project with no captured metrics', () => {
      renderWithRouter(<ProjectCard project={mockProject} latestPeriod={null} />);
      expect(screen.getByLabelText(/No metrics captured yet/i)).toBeDefined();
    });

    it('shows warning for LIVE project with old metrics', () => {
      renderWithRouter(<ProjectCard project={mockProject} latestPeriod={oldPeriod()} />);
      expect(screen.getByLabelText(/No fresh metrics since/i)).toBeDefined();
    });

    it('does NOT show warning for LIVE project with recent metrics', () => {
      renderWithRouter(<ProjectCard project={mockProject} latestPeriod={currentPeriod()} />);
      expect(screen.queryByLabelText(/No (fresh|metrics)/i)).toBeNull();
    });

    it('does NOT show warning for FINISHED project even with stale metrics', () => {
      const finished: Project = { ...mockProject, status: 'finished' };
      renderWithRouter(<ProjectCard project={finished} latestPeriod={oldPeriod()} />);
      expect(screen.queryByLabelText(/No (fresh|metrics)/i)).toBeNull();
    });

    it('does NOT show warning for PROPOSAL project with no metrics', () => {
      const proposal: Project = { ...mockProject, status: 'proposal' };
      renderWithRouter(<ProjectCard project={proposal} latestPeriod={null} />);
      expect(screen.queryByLabelText(/No (fresh|metrics)/i)).toBeNull();
    });
  });
});
