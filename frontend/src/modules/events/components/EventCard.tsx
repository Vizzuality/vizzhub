import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, ExternalLink, MapPin, MessageSquareText, Users } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import { useTheme } from 'next-themes';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { StarRating } from './StarRating';
import { RsvpChips } from './RsvpChips';
import { eventsApi } from '../services/events';
import { formatEventDateRange, getThemeColor } from '../utils/constants';
import type { EventSummary, RsvpStatus, UserSummary } from '../types/events';

interface EventCardProps {
  readonly event: EventSummary;
}

export function EventCard({ event }: EventCardProps): JSX.Element {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const themeColor = getThemeColor(event.theme_primary, isDark);
  const queryClient = useQueryClient();
  const [hydratedNames, setHydratedNames] =
    useState<Record<RsvpStatus, UserSummary[]> | null>(null);

  const prefetchNames = async (): Promise<void> => {
    if (hydratedNames) return;
    const detail = await queryClient.fetchQuery({
      queryKey: queryKeys.events.detail(event.id),
      queryFn: () => eventsApi.get(event.id),
    });
    setHydratedNames(detail.rsvps);
  };

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow flex flex-col"
      onClick={() => navigate(`/events/${event.id}`)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-sm leading-tight line-clamp-2">
            {event.name}
          </h3>
          <StarRating value={event.rating} size={14} />
        </div>
        <div className="flex flex-wrap gap-1 mt-1">
          <Badge variant="outline" className="text-xs">
            {event.event_type}
          </Badge>
          <Badge
            variant="outline"
            className="text-xs"
            style={{ borderColor: themeColor, color: themeColor }}
          >
            {event.theme_primary}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0 flex-1 flex flex-col justify-between gap-3">
        <div className="space-y-1.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Calendar size={12} />
            <span>{formatEventDateRange(event.start_date, event.end_date)}</span>
          </div>
          {(event.location_city || event.location_country) && (
            <div className="flex items-center gap-1.5">
              <MapPin size={12} />
              <span>
                {[event.location_city, event.location_country]
                  .filter(Boolean)
                  .join(', ')}
              </span>
            </div>
          )}
          {event.attendee_names.length > 0 && (
            <div className="flex items-start gap-1.5">
              <Users size={12} className="mt-0.5 shrink-0" />
              <span className="line-clamp-2">
                {event.attendee_names.join(', ')}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {formatCurrency(Number(event.total_cost))}
            </span>
            {event.observations && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MessageSquareText size={14} />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs text-xs">
                    {event.observations}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          {event.url && (
            <a
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 -mr-2 rounded-md hover:bg-muted transition-colors"
            >
              <ExternalLink size={14} />
              <span>Link</span>
            </a>
          )}
        </div>
        <div
          className="mt-3 pt-3 border-t"
          onClick={(e) => e.stopPropagation()}
        >
          <RsvpChips
            eventId={event.id}
            counts={event.rsvp_counts}
            myStatus={event.my_rsvp_status}
            names={hydratedNames ?? undefined}
            onHover={() => { void prefetchNames(); }}
            size="sm"
          />
        </div>
      </CardContent>
    </Card>
  );
}
