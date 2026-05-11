import { useState, useEffect, useMemo } from 'react';
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
import { useEvent, useBatchAttendees, type AttendeeBatch } from '../hooks/useEvent';
import { useCreateEvent, useUpdateEvent, useDeleteEvent } from '../hooks/useEvents';
import { useEventOptions } from '../hooks/useEventOptions';
import { StarRating } from './StarRating';
import { AttendeesPicker, type LocalAttendee } from './AttendeesPicker';
import type { Attendee, EventCreate } from '../types/events';

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
  other_costs: string;
  rating: number | null;
  attending: 'yes' | 'no' | 'maybe' | null;
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
  other_costs: '0',
  rating: null,
  attending: null,
  url: '',
  observations: '',
};

function attendeeToLocal(a: Attendee): LocalAttendee {
  return {
    user_id: a.user_id,
    role: a.role,
    cost: a.cost == null ? null : Number(a.cost),
    _persistedId: a.id,
    user_name: a.user_name,
    user_email: a.user_email,
    functional_area: a.functional_area,
  };
}

function computeBatch(
  current: LocalAttendee[],
  original: LocalAttendee[],
): AttendeeBatch {
  const origByUser = new Map(original.map((a) => [a.user_id, a]));
  const currByUser = new Map(current.map((a) => [a.user_id, a]));

  const toAdd = current
    .filter((a) => !a._persistedId)
    .map((a) => ({ user_id: a.user_id, role: a.role, cost: a.cost }));

  const toRemove = original
    .filter((a) => !currByUser.has(a.user_id))
    .map((a) => a.user_id);

  const toUpdate: AttendeeBatch['toUpdate'] = [];
  for (const a of current) {
    if (!a._persistedId) continue;
    const prev = origByUser.get(a.user_id);
    if (!prev) continue;
    const changes: { role?: string; cost?: number | null } = {};
    if (prev.role !== a.role) changes.role = a.role;
    if ((prev.cost ?? null) !== (a.cost ?? null)) changes.cost = a.cost;
    if (Object.keys(changes).length > 0) {
      toUpdate.push({ user_id: a.user_id, changes });
    }
  }

  return { toAdd, toRemove, toUpdate };
}

export function EventForm({ eventId, onClose }: EventFormProps): JSX.Element {
  const isNew = eventId === 'new';
  const editId = !isNew && eventId ? eventId : '';

  const { data: existingEvent, isLoading } = useEvent(editId);
  const { data: options } = useEventOptions();
  const createEvent = useCreateEvent();
  const updateEvent = useUpdateEvent();
  const deleteEvent = useDeleteEvent();
  const batchAttendees = useBatchAttendees();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [attendees, setAttendees] = useState<LocalAttendee[]>([]);
  const [originalAttendees, setOriginalAttendees] = useState<LocalAttendee[]>([]);
  const [currentEventId, setCurrentEventId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
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
        other_costs: String(existingEvent.other_costs ?? 0),
        rating: existingEvent.rating,
        attending: existingEvent.attending,
        url: existingEvent.url ?? '',
        observations: existingEvent.observations ?? '',
      });
      const mapped = existingEvent.attendees.map(attendeeToLocal);
      setAttendees(mapped);
      setOriginalAttendees(mapped);
    }
  }, [existingEvent, isNew]);

  const totalCost = useMemo(() => {
    const other = Number(form.other_costs) || 0;
    const sum = attendees.reduce((acc, a) => acc + (a.cost ?? 0), 0);
    return other + sum;
  }, [form.other_costs, attendees]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]): void => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setWarning(null);

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
      other_costs: Number(form.other_costs) || 0,
      rating: form.rating,
      attending: form.attending,
      url: form.url || null,
      observations: form.observations || null,
    };

    const extractDetail = (err: unknown): string | undefined =>
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;

    let targetId: string;
    try {
      if (isNew && !currentEventId) {
        const created = await createEvent.mutateAsync(payload);
        targetId = created.id;
        setCurrentEventId(created.id);
      } else {
        const existingId = editId || currentEventId || '';
        targetId = existingId;
        await updateEvent.mutateAsync({ id: existingId, data: payload });
      }
    } catch (err) {
      setError(extractDetail(err) ?? 'Something went wrong.');
      return;
    }

    const batch = computeBatch(attendees, originalAttendees);
    const hasBatchWork =
      batch.toAdd.length > 0 || batch.toRemove.length > 0 || batch.toUpdate.length > 0;

    if (hasBatchWork) {
      try {
        const result = await batchAttendees.mutateAsync({
          eventId: targetId,
          batch,
        });
        if (result.failed.length > 0) {
          setWarning(
            `Event saved, but ${result.failed.length} attendee change(s) failed. Please retry.`,
          );
          // Refresh original baseline from current server state would require a refetch;
          // keep form open so the user can retry.
          return;
        }
      } catch (err) {
        setWarning(
          extractDetail(err) ?? 'Event saved, but attendee updates failed.',
        );
        return;
      }
    }

    onClose();
  };

  const handleDelete = (): void => {
    const deleteId = editId || currentEventId;
    if (!deleteId) return;
    deleteEvent.mutate(deleteId, { onSuccess: onClose });
  };

  const isPending =
    createEvent.isPending || updateEvent.isPending || batchAttendees.isPending;

  const showDeleteButton = !isNew || !!currentEventId;
  const inCreateMode = isNew && !currentEventId;

  let submitLabel = 'Save';
  if (isPending) submitLabel = 'Saving...';
  else if (inCreateMode) submitLabel = 'Create';

  return (
    <Dialog open={eventId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{inCreateMode ? 'New Event' : 'Edit Event'}</DialogTitle>
        </DialogHeader>

        {isNew || !isLoading ? (
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

            {/* Attending */}
            <div className="space-y-1.5">
              <Label>Attending</Label>
              <div
                role="radiogroup"
                aria-label="Attending"
                className="flex flex-wrap gap-2"
              >
                {(
                  [
                    { value: null, label: 'Sin decidir' },
                    { value: 'yes', label: 'Yes' },
                    { value: 'maybe', label: 'Maybe' },
                    { value: 'no', label: 'No' },
                  ] as const
                ).map((opt) => {
                  const id = `evt-attending-${opt.value ?? 'none'}`;
                  const checked = form.attending === opt.value;
                  return (
                    <label
                      key={id}
                      htmlFor={id}
                      className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm cursor-pointer ${
                        checked
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input hover:bg-accent'
                      }`}
                    >
                      <input
                        id={id}
                        type="radio"
                        name="evt-attending"
                        checked={checked}
                        onChange={() => setField('attending', opt.value)}
                        className="sr-only"
                      />
                      {opt.label}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Other costs + Rating */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="evt-other-costs">Other costs (EUR)</Label>
                <Input
                  id="evt-other-costs"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.other_costs}
                  onChange={(e) => setField('other_costs', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Event-level costs not tied to an attendee (venue, booth, etc.).
                </p>
                <div className="flex items-center justify-between pt-1 text-sm">
                  <span className="text-muted-foreground">Total</span>
                  <span className="font-medium">
                    {`€${totalCost.toFixed(2)}`}
                  </span>
                </div>
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

            {/* Attendees (always visible, collects batch locally) */}
            <div className="border-t pt-4">
              <AttendeesPicker
                attendees={attendees}
                onChange={setAttendees}
              />
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            {warning && (
              <p className="text-sm text-amber-600 dark:text-amber-400">{warning}</p>
            )}

            <DialogFooter className="flex !justify-between">
              {showDeleteButton ? (
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
                  {submitLabel}
                </Button>
              </div>
            </DialogFooter>
          </form>
        ) : (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
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
