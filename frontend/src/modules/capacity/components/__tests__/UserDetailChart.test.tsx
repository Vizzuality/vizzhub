import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UserDetailChart } from '@/modules/capacity/components/UserDetailChart';
import type { PeriodProjectInsight, ReportableUser } from '@/modules/capacity/types/capacity';

const USERS: ReportableUser[] = [{ id: 'u1', name: 'Alice Smith' }];

describe('UserDetailChart', () => {
  it('renders Other row in the legend when present', () => {
    const data: PeriodProjectInsight[] = [
      {
        period: '2026-01',
        projects: [
          { project_id: 'p1', name: 'Alpha', percentage: 0.6, type: 'billable' },
          { project_id: '__other__', name: 'Other', percentage: 0.2, type: 'other' },
        ],
        absence_pct: 0.2,
        other_pct: 0.2,
      },
    ];

    render(
      <UserDetailChart
        data={data}
        userId="u1"
        users={USERS}
        onUserChange={() => {}}
        startDate="2026-01"
        endDate="2026-01"
        onRangeChange={() => {}}
      />,
    );

    // The Other row is NOT shown in the project legend (it's the shared "Other" lane)
    const projectLegend = screen.queryByText('Other');
    expect(projectLegend).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Absence')).toBeInTheDocument();
  });

  it('renders empty state when no userId selected', () => {
    render(
      <UserDetailChart
        data={[]}
        userId=""
        users={USERS}
        onUserChange={() => {}}
        startDate="2026-01"
        endDate="2026-01"
        onRangeChange={() => {}}
      />,
    );

    expect(screen.getByText('Select a user to view project breakdown')).toBeInTheDocument();
  });
});
