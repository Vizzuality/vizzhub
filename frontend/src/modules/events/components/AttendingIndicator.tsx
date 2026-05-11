import { ATTENDING_DOT_COLORS, ATTENDING_LABELS } from '../utils/constants';
import type { Attending } from '../types/events';

interface AttendingIndicatorProps {
  readonly value: Attending;
}

export function AttendingIndicator({ value }: AttendingIndicatorProps): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${ATTENDING_DOT_COLORS[value]}`} />
      <span className="text-foreground">{ATTENDING_LABELS[value]}</span>
    </span>
  );
}
