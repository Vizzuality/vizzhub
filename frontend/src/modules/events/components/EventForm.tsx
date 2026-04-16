import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useEvent, useAddAttendees, useRemoveAttendee } from '../hooks/useEvent';
import { useCreateEvent, useUpdateEvent, useDeleteEvent } from '../hooks/useEvents';
import { useEventOptions } from '../hooks/useEventOptions';
import { StarRating } from './StarRating';
import { AttendeesPicker } from './AttendeesPicker';
import type { EventCreate } from '../types/events';

const NONE_SENTINEL = '__none__';

interface EventFormProps {
  readonly eventId: string | null;
  readonly onClose: () => void;
}

interface FormState {
  name: string;
  event_type: string;
  theme_primary: string;
  theme_secondary: string;
  region_focus: string;
  start_date: string;
  end_date: string;
  location_city: string;
  location_country: string;
  cost: string;
  rating: number | null;
  url: string;
  observations: string;
}

const INITIAL_FORM: FormState = {
  name: '',
  event_type: 'Conference',
  theme_primary: 'Climate',
  theme_secondary: NONE_SENTINEL,
  region_focus: 'Global',
  start_date: '',
  end_date: '',
  location_city: '',
  location_country: '',
  cost: '0',
  rating: null,
  url: '',
  observations: '',
};

export function EventForm({ eventId, onClose }: EventFormProps): JSX.Element {
  const isNew = eventId === 'new';
  const editId = !isNew && eventId ? eventId : '';

  const { data: existingEvent, isLoading } = useEvent(editId);
  const { data: options } = useEventOptions();
  const createEvent = useCreateEvent();
  const updateEvent = useUpdateEvent();
  const deleteEvent = useDeleteEvent();
  const addAttendees = useAddAttendees();
  const removeAttendee = useRemoveAttendee();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (existingEvent && !isNew) {
      setForm({
        name: existingEvent.name,
        event_type: existingEvent.event_type,
        theme_primary: existingEvent.theme_primary,
        theme_secondary: existingEvent.theme_secondary ?? NONE_SENTINEL,
        region_focus: existingEvent.region_focus,
        start_date: existingEvent.start_date,
        end_date: existingEvent.end_date ?? '',
        location_city: existingEvent.location_city ?? '',
        location_country: existingEvent.location_country ?? '',
        cost: String(existingEvent.cost ?? 0),
        rating: existingEvent.rating,
        url: existingEvent.url ?? '',
        observations: existingEvent.observations ?? '',
      });
    }
  }, [existingEvent, isNew]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]): void => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Name is required.');
      return;
    }
    if (!form.start_date) {
      setError('Start date is required.');
      return;
    }

    const payload: EventCreate = {
      name: form.name.trim(),
      event_type: form.event_type as EventCreate['event_type'],
      theme_primary: form.theme_primary as EventCreate['theme_primary'],
      theme_secondary:
        form.theme_secondary === NONE_SENTINEL
          ? null
          : (form.theme_secondary as EventCreate['theme_primary']),
      region_focus: form.region_focus as EventCreate['region_focus'],
      start_date: form.start_date,
      end_date: form.end_date || null,
      location_city: form.location_city || null,
      location_country: form.location_country || null,
      cost: Number(form.cost) || 0,
      rating: form.rating,
      url: form.url || null,
      observations: form.observations || null,
    };

    const onError = (err: unknown): void => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail ?? 'Something went wrong.');
    };

    if (isNew) {
      createEvent.mutate(payload, { onSuccess: onClose, onError });
    } else {
      updateEvent.mutate(
        { id: editId, data: payload },
        { onSuccess: onClose, onError },
      );
    }
  };

  const handleDelete = (): void => {
    deleteEvent.mutate(editId, { onSuccess: onClose });
  };

  const isPending = createEvent.isPending || updateEvent.isPending;

  const handleAddAttendees = (
    attendees: { user_id: string; role: string }[],
  ): void => {
    addAttendees.mutate({ eventId: editId, attendees });
  };

  const handleRemoveAttendee = (userId: string): void => {
    removeAttendee.mutate({ eventId: editId, userId });
  };

  return (
    <Dialog open={eventId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isNew ? 'New Event' : 'Edit Event'}</DialogTitle>
        </DialogHeader>

        {!isNew && isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div className="space-y-1.5">
              <Label htmlFor="evt-name">Name *</Label>
              <Input
                id="evt-name"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                placeholder="Event name"
              />
            </div>

            {/* Type + Region */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select
                  value={form.event_type}
                  onValueChange={(v) => setField('event_type', v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(options?.event_types ?? []).map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Region</Label>
                <Select
                  value={form.region_focus}
                  onValueChange={(v) => setField('region_focus', v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(options?.regions ?? []).map((r) => (
                      <SelectItem key={r} value={r}>{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Theme primary + secondary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Primary Theme</Label>
                <Select
                  value={form.theme_primary}
                  onValueChange={(v) => setField('theme_primary', v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(options?.themes ?? []).map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Secondary Theme</Label>
                <Select
                  value={form.theme_secondary}
                  onValueChange={(v) => setField('theme_secondary', v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE_SENTINEL}>None</SelectItem>
                    {(options?.themes ?? []).map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="evt-start">Start Date *</Label>
                <Input
                  id="evt-start"
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setField('start_date', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="evt-end">End Date</Label>
                <Input
                  id="evt-end"
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setField('end_date', e.target.value)}
                />
              </div>
            </div>

            {/* Location */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="evt-city">City</Label>
                <Input
                  id="evt-city"
                  value={form.location_city}
                  onChange={(e) => setField('location_city', e.target.value)}
                  placeholder="City"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="evt-country">Country</Label>
                <Input
                  id="evt-country"
                  value={form.location_country}
                  onChange={(e) => setField('location_country', e.target.value)}
                  placeholder="Country"
                />
              </div>
            </div>

            {/* Cost + Rating */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="evt-cost">Cost (EUR)</Label>
                <Input
                  id="evt-cost"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.cost}
                  onChange={(e) => setField('cost', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Rating</Label>
                <div className="pt-1">
                  <StarRating
                    value={form.rating}
                    onChange={(v) => setField('rating', v)}
                    size={20}
                  />
                </div>
              </div>
            </div>

            {/* URL */}
            <div className="space-y-1.5">
              <Label htmlFor="evt-url">URL</Label>
              <Input
                id="evt-url"
                type="url"
                value={form.url}
                onChange={(e) => setField('url', e.target.value)}
                placeholder="https://..."
              />
            </div>

            {/* Observations */}
            <div className="space-y-1.5">
              <Label htmlFor="evt-obs">Observations</Label>
              <Textarea
                id="evt-obs"
                rows={3}
                value={form.observations}
                onChange={(e) => setField('observations', e.target.value)}
                placeholder="Notes about this event..."
              />
            </div>

            {/* Attendees (edit only) */}
            {!isNew && existingEvent && (
              <div className="border-t pt-4">
                <AttendeesPicker
                  attendees={existingEvent.attendees}
                  onAdd={handleAddAttendees}
                  onRemove={handleRemoveAttendee}
                />
              </div>
            )}

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <DialogFooter className="flex !justify-between">
              {!isNew ? (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => setShowDeleteConfirm(true)}
                >
                  Delete
                </Button>
              ) : <span />}
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending
                    ? 'Saving...'
                    : isNew
                      ? 'Create'
                      : 'Save'}
                </Button>
              </div>
            </DialogFooter>
          </form>
        )}
      </DialogContent>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete event?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{form.name}&quot; and all its attendees.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => { e.preventDefault(); handleDelete(); }}
            >
              {deleteEvent.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}
