import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import EventsDashboard from '../EventsDashboard';

const mockUseEventStats = vi.fn((_params: unknown) => ({ data: undefined, isLoading: false }));

vi.mock('../../hooks/useEventStats', () => ({
  useEventStats: (params: unknown) => mockUseEventStats(params),
}));
vi.mock('../../hooks/useEventOptions', () => ({
  useEventOptions: () => ({ data: { years_with_data: [2026, 2025] } }),
}));

function renderAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <EventsDashboard />
    </MemoryRouter>,
  );
}

describe('EventsDashboard filters', () => {
  beforeEach(() => {
    mockUseEventStats.mockClear();
  });

  it('passes year and attending from the URL to the stats query', () => {
    renderAt('/events/dashboard?year=2025&attending=attended');
    expect(mockUseEventStats).toHaveBeenLastCalledWith({ year: 2025, attending: 'attended' });
  });

  it('omits unset filters instead of sending undefined', () => {
    renderAt('/events/dashboard');
    expect(mockUseEventStats).toHaveBeenLastCalledWith({});
  });
});
