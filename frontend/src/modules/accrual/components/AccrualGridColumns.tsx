import type { ColumnDef } from '@tanstack/react-table';
import { Link } from 'react-router-dom';
import { AlertTriangle, AlertCircle, Info, Pencil, type LucideIcon } from 'lucide-react';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import { AccrualCell } from '@/modules/accrual/components/AccrualCell';
import { buildCellKey } from '@/modules/accrual/types/accrual';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridLine,
  AccrualGridMonth,
  AccrualHealth,
  AccrualHealthStatus,
  AccrualLineSource,
} from '@/modules/accrual/types/accrual';

// Pixel offsets for each of the 5 sticky-left columns.
// code=0, name=160, projects=360, original=520, value=630
export const STICKY_LEFT_OFFSETS: readonly number[] = [0, 160, 360, 520, 630];

const fmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatAmount(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—';
  const n = Number(val);
  return Number.isNaN(n) ? val : fmt.format(n);
}

function resolveEurAmount(cell: AccrualCellType): number {
  const eur = cell.is_frozen ? cell.frozen_eur_amount : cell.eur_amount;
  return Number(eur) || 0;
}

export function monthLabel(month: number): string {
  return MONTHS_SHORT[month - 1] ?? String(month);
}

export interface MonthColumnMeta {
  readonly year: number;
  readonly month: number;
}

const SOURCE_BADGE: Record<AccrualLineSource, { label: string; cls: string }> = {
  excel: { label: 'Excel', cls: 'bg-sky-100 text-sky-700' },
  team_budget: { label: 'Team budget', cls: 'bg-muted text-muted-foreground' },
  manual: { label: 'Manual', cls: 'bg-violet-100 text-violet-700' },
};

function healthTooltip(health: AccrualHealth): string {
  if (health.diff_pct === null || health.diff_pct === 0) return health.status;
  const isNegative = health.diff_eur?.startsWith('-') ?? false;
  const direction = isNegative ? 'under' : 'over';
  return `Scheduled cells ${Math.abs(health.diff_pct).toFixed(1)}% ${direction} the line value`;
}

const HEALTH_ICON: Record<
  Exclude<AccrualHealthStatus, 'ok'>,
  { Icon: LucideIcon; testId: string; colorClass: string }
> = {
  critical: { Icon: AlertCircle, testId: 'health-critical', colorClass: 'text-red-600' },
  warning: { Icon: AlertTriangle, testId: 'health-warning', colorClass: 'text-amber-500' },
  no_data: { Icon: Info, testId: 'health-no-data', colorClass: 'text-muted-foreground' },
};

function HealthIndicator({ health }: { readonly health: AccrualHealth }): JSX.Element | null {
  if (health.status === 'ok') return null;
  const { Icon, testId, colorClass } = HEALTH_ICON[health.status];
  const title = healthTooltip(health);
  return (
    <Icon data-testid={testId} className={`h-3.5 w-3.5 shrink-0 ${colorClass}`} aria-label={title}>
      <title>{title}</title>
    </Icon>
  );
}

function DataQualityIndicator({ note }: { readonly note: string | null }): JSX.Element | null {
  if (!note) return null;
  return (
    <AlertTriangle
      data-testid="data-quality-warning"
      className="h-3.5 w-3.5 shrink-0 text-amber-500"
      aria-label={note}
    >
      <title>{note}</title>
    </AlertTriangle>
  );
}

function LineCodeCellRenderer({
  line,
  onEditLine,
}: {
  readonly line: AccrualGridLine;
  readonly onEditLine?: (lineId: string) => void;
}): JSX.Element {
  return (
    <span className="flex items-center gap-1.5">
      {onEditLine ? (
        <button
          type="button"
          onClick={() => onEditLine(line.id)}
          className="shrink-0 text-muted-foreground/60 hover:text-foreground"
          title={`Edit ${line.name ?? 'line'}`}
          aria-label={`Edit ${line.name ?? 'line'}`}
        >
          <Pencil className="h-3 w-3" />
        </button>
      ) : null}
      <span className="whitespace-nowrap text-xs text-muted-foreground tabular-nums">
        {line.excel_code ?? '—'}
      </span>
    </span>
  );
}

function LineNameCellRenderer({ line }: { readonly line: AccrualGridLine }): JSX.Element {
  // Only flag non-Excel provenance — Excel is the norm, so badging it is noise.
  const badge = line.source === 'excel' ? null : SOURCE_BADGE[line.source];
  const label = line.name ?? '(unnamed line)';
  // Link the name to its tracker project only when the line maps to exactly one
  // project. For multi-project or unlinked lines the target is ambiguous, so the
  // name stays plain text — the Projects column carries the per-project links.
  const soleProject = line.projects.length === 1 ? line.projects[0] : null;
  const name = soleProject ? (
    <Link
      to={`/tracker/projects/${soleProject.id}`}
      className="block min-w-0 truncate text-sm hover:underline"
      title={line.name ?? undefined}
    >
      {label}
    </Link>
  ) : (
    <span className="block min-w-0 truncate text-sm" title={line.name ?? undefined}>
      {label}
    </span>
  );
  return (
    <span className="flex items-center gap-1.5 min-w-0">
      <HealthIndicator health={line.health} />
      <DataQualityIndicator note={line.data_quality_note} />
      {name}
      {badge ? (
        <span className={`shrink-0 rounded px-1 text-[9px] font-medium ${badge.cls}`}>
          {badge.label}
        </span>
      ) : null}
    </span>
  );
}

function LineProjectsCellRenderer({ line }: { readonly line: AccrualGridLine }): JSX.Element {
  if (line.projects.length === 0) {
    return <span className="text-xs italic text-muted-foreground">no project</span>;
  }
  return (
    <span className="flex flex-wrap items-center gap-1">
      {line.projects.map((p) => (
        <Link
          key={p.id}
          to={`/tracker/projects/${p.id}`}
          className="rounded border px-1 text-[10px] tabular-nums text-muted-foreground hover:bg-muted hover:text-foreground"
          title={p.name}
        >
          {p.code ?? p.name}
        </Link>
      ))}
    </span>
  );
}

function LineOriginalCellRenderer({ line }: { readonly line: AccrualGridLine }): JSX.Element {
  return (
    <span className="text-xs tabular-nums">
      {formatAmount(line.value_orig)}
      {line.value_orig && line.currency ? (
        <span className="ml-1 text-muted-foreground">{line.currency}</span>
      ) : null}
      {line.rate ? (
        <span className="ml-1 text-muted-foreground" title="Rate for this line (foreign per €)">
          @ {Number(line.rate).toFixed(4)}
        </span>
      ) : null}
    </span>
  );
}

function diffBadgeClass(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 5) return 'text-emerald-700';
  if (abs <= 20) return 'text-amber-600';
  return 'text-red-600';
}

function LineValueCellRenderer({ line }: { readonly line: AccrualGridLine }): JSX.Element {
  const { diff_pct, diff_eur } = line.health;
  const isNegative = diff_eur?.startsWith('-') ?? false;
  return (
    <span className="flex items-baseline gap-1 text-xs tabular-nums">
      <span>{formatAmount(line.value_eur)}</span>
      {diff_pct !== null && Math.abs(diff_pct) > 0.5 ? (
        <span className={`${diffBadgeClass(diff_pct)} text-[10px]`}>
          {isNegative ? '−' : '+'}
          {Math.abs(diff_pct).toFixed(0)}%
        </span>
      ) : null}
    </span>
  );
}

// Index cells by `${line_id}:${year}:${month}` for constant-time lookup.
function indexCells(cells: AccrualCellType[]): Map<string, AccrualCellType> {
  const map = new Map<string, AccrualCellType>();
  for (const c of cells) {
    if (c.line_id) map.set(buildCellKey(c.line_id, c.year, c.month), c);
  }
  return map;
}

export function buildColumns(
  months: AccrualGridMonth[],
  cells: AccrualCellType[],
  onCellChange: (lineId: string, year: number, month: number, amount: string) => void,
  canEdit: boolean,
  failedCells: ReadonlySet<string> | undefined,
  onEditLine?: (lineId: string) => void,
): ColumnDef<AccrualGridLine>[] {
  const cellIndex = indexCells(cells);
  const sticky: ColumnDef<AccrualGridLine>[] = [
    {
      id: 'code',
      header: 'Code',
      size: 160,
      cell: ({ row }) => <LineCodeCellRenderer line={row.original} onEditLine={onEditLine} />,
    },
    {
      id: 'name',
      header: 'Line',
      size: 200,
      cell: ({ row }) => <LineNameCellRenderer line={row.original} />,
    },
    {
      id: 'projects',
      header: 'Projects',
      size: 160,
      cell: ({ row }) => <LineProjectsCellRenderer line={row.original} />,
    },
    {
      id: 'original',
      header: 'Original',
      size: 110,
      cell: ({ row }) => <LineOriginalCellRenderer line={row.original} />,
    },
    {
      id: 'value_eur',
      header: 'Value €',
      size: 110,
      cell: ({ row }) => <LineValueCellRenderer line={row.original} />,
    },
  ];

  const monthCols: ColumnDef<AccrualGridLine>[] = months.map((m) => ({
    id: `month_${m.year}_${m.month}`,
    header: () => {
      const showYear = m.month === 1;
      return (
        <div className="flex flex-col leading-none gap-0.5">
          {showYear && <span className="text-[10px] text-muted-foreground">{m.year}</span>}
          <span>{monthLabel(m.month)}</span>
        </div>
      );
    },
    size: 90,
    meta: { year: m.year, month: m.month } satisfies MonthColumnMeta,
    cell: ({ row }) => {
      const line = row.original;
      const key = buildCellKey(line.id, m.year, m.month);
      const cell = cellIndex.get(key);
      return (
        <AccrualCell
          amount={cell?.amount ?? '0'}
          eurAmount={cell?.frozen_eur_amount ?? cell?.eur_amount ?? null}
          isOverride={cell?.is_manual_override ?? false}
          isFrozen={cell?.is_frozen ?? false}
          canEdit={canEdit}
          onChange={(newAmount) => onCellChange(line.id, m.year, m.month, newAmount)}
          onError={failedCells?.has(key) ?? false}
          source={cell?.source}
        />
      );
    },
  }));

  return [...sticky, ...monthCols];
}

// Totals row computation helper — exported for use in AccrualGrid footer.
export function computeMonthTotals(
  months: AccrualGridMonth[],
  lines: AccrualGridLine[],
  cells: AccrualCellType[],
): Map<string, number> {
  const cellIndex = indexCells(cells);
  const result = new Map<string, number>();
  for (const m of months) {
    let total = 0;
    for (const l of lines) {
      const cell = cellIndex.get(buildCellKey(l.id, m.year, m.month));
      if (cell) total += resolveEurAmount(cell);
    }
    result.set(`${m.year}_${m.month}`, total);
  }
  return result;
}
