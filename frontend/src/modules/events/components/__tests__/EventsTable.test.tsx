import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EventsTable } from '../EventsTable';
import type { EventSummary } from '../../types/events';

const events: EventSummary[] = [
  {
    id: 'e1',
    name: 'First',
    event_type: 'Conference',
    theme_primary: 'Climate',
    theme_secondary: null,
    region_focus: 'Global',
    location_city: 'Madrid',
    location_country: 'ES',
    start_date: '2026-05-01',
    end_date: null,
    other_costs: 100,
    total_cost: 150,
    rating: 4,
    url: null,
    observations: null,
    created_by: null,
    attendee_count: 2,
    attendee_names: [],
    rsvp_counts: { going: 1, maybe: 0, not_going: 0 },
    my_rsvp_status: null,
    created_at: '',
    updated_at: '',
  },
];

function render_(props: Parameters<typeof EventsTable>[0]) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <EventsTable {...props} />
    </QueryClientProvider>,
  );
}

describe('EventsTable', () => {
  it('renders a row per event', () => {
    render_({
      events,
      onRowClick: () => {},
      sortKey: 'start_date',
      sortDir: 'desc',
      onSortChange: () => {},
    });
    expect(screen.getByText('First')).toBeInTheDocument();
  });

  it('row click calls onRowClick with event id', () => {
    const cb = vi.fn();
    render_({
      events,
      onRowClick: cb,
      sortKey: 'start_date',
      sortDir: 'desc',
      onSortChange: () => {},
    });
    fireEvent.click(screen.getByText('First'));
    expect(cb).toHaveBeenCalledWith('e1');
  });
});
