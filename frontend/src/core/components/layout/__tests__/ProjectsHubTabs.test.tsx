import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProjectsHubTabs } from '../ProjectsHubTabs';

let mockCanPortfolio = false;

vi.mock('@/core/permissions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/core/permissions')>();
  return {
    ...actual,
    usePermission: () => mockCanPortfolio,
  };
});

function renderAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ProjectsHubTabs />
    </MemoryRouter>,
  );
}

describe('ProjectsHubTabs', () => {
  beforeEach(() => {
    mockCanPortfolio = false;
  });

  it('renders three tabs without portfolio permission', () => {
    renderAt('/projects');
    expect(screen.getByRole('link', { name: 'Tracker' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Scorecard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Global Scores' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Portfolio' })).not.toBeInTheDocument();
  });

  it('renders the Portfolio tab with permission', () => {
    mockCanPortfolio = true;
    renderAt('/portfolio');
    expect(screen.getByRole('link', { name: 'Portfolio' })).toBeInTheDocument();
  });

  it('marks only Global Scores active on /scorecard/global', () => {
    renderAt('/scorecard/global');
    expect(screen.getByRole('link', { name: 'Global Scores' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Scorecard' })).not.toHaveAttribute('aria-current');
  });

  it('marks Portfolio active on program detail', () => {
    mockCanPortfolio = true;
    renderAt('/portfolio/programs/abc');
    expect(screen.getByRole('link', { name: 'Portfolio' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });
});
