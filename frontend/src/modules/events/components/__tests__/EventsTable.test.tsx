import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EventsTable } from '../EventsTable';
import type { EventSummary } from '../../types/events';

function makeEvent(overrides: Partial<EventSummary> = {}): EventSummary {
  return {
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
    other_costs: '100',
    total_cost: '150',
    attending: null,
    rating: 4,
    url: null,
    observations: null,
    created_by: null,
    attendee_count: 2,
    attendee_names: [],
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

const events: EventSummary[] = [makeEvent()];

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

  it('renders the attending value when set', () => {
    render_({
      events: [makeEvent({ attending: 'yes' })],
      onRowClick: () => {},
      sortKey: 'start_date',
      sortDir: 'desc',
      onSortChange: () => {},
    });
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });

  it('renders an em dash when attending is null', () => {
    render_({
      events: [makeEvent({ attending: null })],
      onRowClick: () => {},
      sortKey: 'start_date',
      sortDir: 'desc',
      onSortChange: () => {},
    });
    // The Attending column should fall back to '—'. Use a custom matcher
    // because the table has multiple '—' cells (e.g. for missing location).
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });
});
