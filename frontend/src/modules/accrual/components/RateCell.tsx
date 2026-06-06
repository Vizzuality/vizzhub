import { useRef, useState } from 'react';
import type { AccrualGridLine } from '@/modules/accrual/types/accrual';

interface RateCellProps {
  readonly line: AccrualGridLine;
  readonly canEdit: boolean;
  readonly onChange: (lineId: string, rate: string | null) => void;
}

function isEur(line: AccrualGridLine): boolean {
  return !line.currency || line.currency.toUpperCase() === 'EUR' || line.currency === 'euro';
}

/** Editable per-line FX rate. Override (line.rate) shows green; an editable line still
 * following the period rate shows an interactive accent colour (so it reads as
 * editable, not read-only); a non-editable / EUR line shows muted. */
export function RateCell({ line, canEdit, onChange }: RateCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const cancelRef = useRef(false);
  const hasOverride = line.rate !== null;
  const display = hasOverride ? Number(line.rate).toFixed(4) : null;
  const periodDisplay = line.period_rate === null ? '—' : Number(line.period_rate).toFixed(4);

  if (isEur(line)) {
    return <span className="text-muted-foreground">1.0000</span>;
  }

  let colorClass = 'text-muted-foreground';
  if (hasOverride) {
    colorClass = 'font-medium text-[var(--score-green)]';
  } else if (canEdit) {
    colorClass = 'text-[var(--chart-2)]';
  }

  if (editing && canEdit) {
    return (
      <input
        type="number"
        step="0.0001"
        min="0"
        autoFocus
        defaultValue={hasOverride ? String(line.rate) : ''}
        aria-label="FX rate override"
        className="h-7 w-20 rounded border bg-background px-1 text-right tabular-nums"
        onBlur={(e) => {
          if (cancelRef.current) {
            cancelRef.current = false;
            setEditing(false);
            return;
          }
          setEditing(false);
          const raw = e.target.value.trim();
          onChange(line.id, raw === '' ? null : raw);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
          if (e.key === 'Escape') {
            cancelRef.current = true;
            (e.target as HTMLInputElement).blur();
          }
        }}
      />
    );
  }

  return (
    <button
      type="button"
      disabled={!canEdit}
      onClick={() => setEditing(true)}
      className={`tabular-nums ${canEdit ? 'cursor-text hover:underline' : 'cursor-default'} ${colorClass}`}
      title={hasOverride ? 'CEO override — click to edit' : 'Following period rate — click to override'}
    >
      {hasOverride ? display : periodDisplay}
    </button>
  );
}
