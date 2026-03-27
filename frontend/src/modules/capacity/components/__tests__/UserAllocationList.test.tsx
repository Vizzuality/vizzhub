import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';
import type { UserAllocation } from '@/modules/capacity/types/allocation';

const MOCK_USERS: UserAllocation[] = [
  {
    user_id: '1',
    name: 'Alice Smith',
    avg_billable_projects: 2.33,
    total_distinct_projects: 4,
    segments: [
      {
        project_id: 'p1',
        project_name: 'Alpha',
        avg_percentage: 0.4,
        months_active: ['2026-03', '2026-02', '2026-01'],
        type: 'billable',
      },
      {
        project_id: 'p2',
        project_name: 'Beta',
        avg_percentage: 0.2,
        months_active: ['2026-03', '2026-02'],
        type: 'billable',
      },
      {
        project_id: 'p3',
        project_name: 'Vacation',
        avg_percentage: 0.1,
        months_active: ['2026-01'],
        type: 'absence',
      },
      {
        project_id: 'p4',
        project_name: 'Internal',
        avg_percentage: 0.3,
        months_active: ['2026-03', '2026-02', '2026-01'],
        type: 'other',
      },
    ],
  },
];

function generateUsers(count: number): UserAllocation[] {
  return Array.from({ length: count }, (_, i) => ({
    user_id: `u${i}`,
    name: `User ${i}`,
    avg_billable_projects: count - i,
    total_distinct_projects: count - i,
    segments: [
      {
        project_id: 'p1',
        project_name: 'Project',
        avg_percentage: 0.5,
        months_active: ['2026-01'],
        type: 'billable' as const,
      },
    ],
  }));
}

describe('UserAllocationList', () => {
  it('renders user name and stats', () => {
    render(<UserAllocationList users={MOCK_USERS} />);
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    expect(screen.getByText(/avg 2.33 projects/)).toBeInTheDocument();
    expect(screen.getByText(/4 total/)).toBeInTheDocument();
  });

  it('shows empty message when no users', () => {
    render(<UserAllocationList users={[]} />);
    expect(screen.getByText('No allocation data available.')).toBeInTheDocument();
  });

  it('paginates at 10 users with show more button', () => {
    const users = generateUsers(25);
    render(<UserAllocationList users={users} />);

    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(10);
    const showMore = screen.getByText(/Show more/);
    expect(showMore).toHaveTextContent('15 remaining');

    fireEvent.click(showMore);
    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(20);

    fireEvent.click(screen.getByText(/Show more/));
    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(25);
    expect(screen.queryByText(/Show more/)).not.toBeInTheDocument();
  });
});
