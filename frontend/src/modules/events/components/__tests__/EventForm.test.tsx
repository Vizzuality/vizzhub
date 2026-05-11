import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EventForm } from '../EventForm';

const createMock = vi.fn().mockResolvedValue({ id: 'new-id' });
const addAttendeesMock = vi.fn().mockResolvedValue(undefined);
const removeAttendeeMock = vi.fn().mockResolvedValue(undefined);
const updateAttendeeMock = vi.fn().mockResolvedValue({});
const updateMock = vi.fn().mockResolvedValue({ id: 'existing-id' });
const deleteMock = vi.fn().mockResolvedValue(undefined);
const getMock = vi.fn();

vi.mock('../../services/events', () => ({
  eventsApi: {
    get: (...a: unknown[]) => getMock(...a),
    create: (...a: unknown[]) => createMock(...a),
    update: (...a: unknown[]) => updateMock(...a),
    delete: (...a: unknown[]) => deleteMock(...a),
    addAttendees: (...a: unknown[]) => addAttendeesMock(...a),
    removeAttendee: (...a: unknown[]) => removeAttendeeMock(...a),
    updateAttendee: (...a: unknown[]) => updateAttendeeMock(...a),
  },
}));

vi.mock('@/core/hooks/useUsers', () => ({
  useUserSummaries: () => ({
    data: [
      { id: 'u1', first_name: 'Alice', last_name: 'X', email: 'a@x', active: true },
    ],
  }),
}));

vi.mock('../../hooks/useEventOptions', () => ({
  useEventOptions: () => ({
    data: {
      event_types: ['Conference'],
      themes: ['Climate'],
      regions: ['Global'],
      attendee_roles: ['Attendee'],
    },
  }),
}));

function renderForm(eventId: string | null) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <EventForm eventId={eventId} onClose={() => {}} />
    </QueryClientProvider>,
  );
}

describe('EventForm create flow', () => {
  it('renders AttendeesPicker on create', () => {
    renderForm('new');
    expect(screen.getByText(/Attendees/i)).toBeInTheDocument();
  });

  it('submits attending=yes when the Yes radio is selected', async () => {
    const user = userEvent.setup();
    renderForm('new');

    await user.type(screen.getByLabelText(/^Name \*$/), 'Test Event');
    await user.type(screen.getByLabelText(/^Start Date \*$/), '2026-06-15');
    await user.click(screen.getByLabelText(/^Yes$/));
    await user.click(screen.getByRole('button', { name: /^Create$/ }));

    await vi.waitFor(() => {
      expect(createMock).toHaveBeenCalled();
    });
    expect(createMock).toHaveBeenCalledWith(
      expect.objectContaining({ attending: 'yes' }),
    );
  });
});
