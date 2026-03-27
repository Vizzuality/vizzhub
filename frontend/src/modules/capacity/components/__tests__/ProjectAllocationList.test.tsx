import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProjectAllocationList } from '@/modules/capacity/components/ProjectAllocationList';
import type { ProjectAllocation } from '@/modules/capacity/types/allocation';

const MOCK_PROJECTS: ProjectAllocation[] = [
  {
    project_id: 'p1',
    name: 'Alpha',
    avg_people: 3.5,
    total_distinct_people: 5,
    segments: [
      {
        user_id: 'u1',
        user_name: 'Alice Smith',
        avg_percentage: 0.4,
        months_active: ['2026-03', '2026-02'],
      },
    ],
  },
];

function generateProjects(count: number): ProjectAllocation[] {
  return Array.from({ length: count }, (_, i) => ({
    project_id: `p${i}`,
    name: `Project ${i}`,
    avg_people: count - i,
    total_distinct_people: count - i,
    segments: [
      {
        user_id: `u${i}`,
        user_name: `User ${i}`,
        avg_percentage: 0.5,
        months_active: ['2026-01'],
      },
    ],
  }));
}

describe('ProjectAllocationList', () => {
  it('renders project name and stats', () => {
    render(<ProjectAllocationList projects={MOCK_PROJECTS} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText(/avg 3.5 people/)).toBeInTheDocument();
    expect(screen.getByText(/5 total/)).toBeInTheDocument();
  });

  it('shows empty message when no projects', () => {
    render(<ProjectAllocationList projects={[]} />);
    expect(screen.getByText('No project data available.')).toBeInTheDocument();
  });

  it('paginates at 10 projects with show more button', () => {
    const projects = generateProjects(25);
    render(<ProjectAllocationList projects={projects} />);

    expect(screen.getAllByText(/^Project \d+$/)).toHaveLength(10);
    const showMore = screen.getByText(/Show more/);
    expect(showMore).toHaveTextContent('15 remaining');

    fireEvent.click(showMore);
    expect(screen.getAllByText(/^Project \d+$/)).toHaveLength(20);

    fireEvent.click(screen.getByText(/Show more/));
    expect(screen.getAllByText(/^Project \d+$/)).toHaveLength(25);
    expect(screen.queryByText(/Show more/)).not.toBeInTheDocument();
  });
});
