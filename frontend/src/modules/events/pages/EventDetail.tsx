import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Calendar,
  Check,
  ExternalLink,
  Link2,
  MapPin,
  Pencil,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Can, Action } from '@/core/permissions';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import { useEvent } from '../hooks/useEvent';
import { EventForm } from '../components/EventForm';
import { RsvpChips } from '../components/RsvpChips';
import { StarRating } from '../components/StarRating';
import { formatEventDateRange } from '../utils/constants';

export default function EventDetail(): JSX.Element {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: event, isLoading, error } = useEvent(id);
  const [editing, setEditing] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  const copyLink = async (): Promise<void> => {
    await navigator.clipboard.writeText(window.location.href);
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 1500);
  };

  if (isLoading) return <LoadingSpinner />;

  if (error || !event) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/events')}
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to events
        </Button>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">
              {error?.message || 'Event not found'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalCost = Number(event.total_cost);
  const otherCosts = Number(event.other_costs);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/events">
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Back to events
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={copyLink}>
            {linkCopied ? (
              <Check className="w-4 h-4 mr-1.5" />
            ) : (
              <Link2 className="w-4 h-4 mr-1.5" />
            )}
            {linkCopied ? 'Copied' : 'Copy link'}
          </Button>
          <Can do={Action.EVENTS_MANAGE}>
            <Button size="sm" onClick={() => setEditing(true)}>
              <Pencil className="w-4 h-4 mr-1.5" />
              Edit
            </Button>
          </Can>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1.5 flex-1">
              <h1 className="text-2xl font-semibold leading-tight">
                {event.name}
              </h1>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="outline">{event.event_type}</Badge>
                <Badge variant="outline">{event.theme_primary}</Badge>
                {event.theme_secondary && (
                  <Badge variant="outline">{event.theme_secondary}</Badge>
                )}
                <Badge variant="outline">{event.region_focus}</Badge>
              </div>
            </div>
            <StarRating value={event.rating} size={20} />
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div className="flex items-start gap-2">
              <Calendar className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
              <div>
                <div className="text-muted-foreground text-xs">Dates</div>
                <div>{formatEventDateRange(event.start_date, event.end_date)}</div>
              </div>
            </div>

            {(event.location_city || event.location_country) && (
              <div className="flex items-start gap-2">
                <MapPin className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
                <div>
                  <div className="text-muted-foreground text-xs">Location</div>
                  <div>
                    {[event.location_city, event.location_country]
                      .filter(Boolean)
                      .join(', ')}
                  </div>
                </div>
              </div>
            )}

            {event.url && (
              <div className="flex items-start gap-2 sm:col-span-2">
                <ExternalLink className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
                <a
                  href={event.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-foreground hover:underline break-all"
                >
                  {event.url}
                </a>
              </div>
            )}
          </div>

          {event.observations && (
            <div className="text-sm">
              <div className="text-muted-foreground text-xs mb-1">
                Observations
              </div>
              <p className="whitespace-pre-wrap">{event.observations}</p>
            </div>
          )}

          <div className="pt-3 border-t">
            <RsvpChips
              eventId={event.id}
              counts={event.rsvp_counts}
              myStatus={event.my_rsvp_status}
              names={event.rsvps}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <h2 className="text-lg font-semibold">
            Attendees ({event.attendees.length})
          </h2>
        </CardHeader>
        <CardContent>
          {event.attendees.length === 0 ? (
            <p className="text-sm text-muted-foreground">No attendees yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Area</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {event.attendees.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">
                      {a.user_name || a.user_email || '—'}
                    </TableCell>
                    <TableCell>{a.role}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {a.functional_area || '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {a.cost == null
                        ? '—'
                        : formatCurrency(Number(a.cost))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Other costs</span>
            <span>{formatCurrency(otherCosts)}</span>
          </div>
          <div className="flex items-center justify-between text-sm mt-2 pt-2 border-t font-medium">
            <span>Total cost</span>
            <span>{formatCurrency(totalCost)}</span>
          </div>
        </CardContent>
      </Card>

      {editing && (
        <EventForm eventId={event.id} onClose={() => setEditing(false)} />
      )}
    </div>
  );
}
