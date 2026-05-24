import type { ColumnDef } from '@tanstack/react-table';
import { Link } from 'react-router-dom';
import { AlertTriangle, AlertCircle, Info, type LucideIcon } from 'lucide-react';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import { AccrualCell } from '@/modules/accrual/components/AccrualCell';
import { getStatusLabel } from '@/utils/projectStatus';
import { buildCellKey } from '@/modules/accrual/types/accrual';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridMonth,
  AccrualGridProject,
  AccrualHealth,
  AccrualHealthStatus,
} from '@/modules/accrual/types/accrual';

// Pixel offsets for each of the 6 sticky-left columns.
// code=0, name=60, status=260, currency=340, budget=410, budget_eur=540
export const STICKY_LEFT_OFFSETS: readonly number[] = [0, 60, 260, 340, 410, 540];

const fmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatAmount(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—';
  const n = Number(val);
  return Number.isNaN(n) ? val : fmt.format(n);
}

/** Returns the effective EUR amount for a cell, preferring the frozen rate when frozen. */
function resolveEurAmount(cell: AccrualCellType): number {
  const eur = cell.is_frozen ? cell.frozen_eur_amount : cell.eur_amount;
  return Number(eur) || 0;
}

export function monthLabel(month: number): string {
  return MONTHS_SHORT[month - 1] ?? String(month);
}

const STATUS_DOT: Record<string, string> = {
  proposal: 'bg-amber-400',
  live: 'bg-emerald-500',
  finished: 'bg-slate-400',
};

function statusDotClass(status: string): string {
  return STATUS_DOT[status] ?? 'bg-muted-foreground';
}

export interface MonthColumnMeta {
  readonly year: number;
  readonly month: number;
}

function ProjectCodeCellRenderer({ project }: { readonly project: AccrualGridProject }): JSX.Element {
  return (
    <span className="truncate text-xs text-muted-foreground tabular-nums" title={project.code ?? undefined}>
      {project.code ?? '—'}
    </span>
  );
}

const HEALTH_REASON_LABELS: Record<string, string> = {
  multi_project_dup_code: 'Code shared with sibling projects (split contract)',
  value_divergence: 'Σ accrual cells diverges from team budget',
  no_cells: 'Team budget set but Excel data missing — accrual blank',
  no_excel_data: 'No Excel match — needs mapping or uniform fallback',
};

function healthTooltip(health: AccrualHealth): string {
  const parts: string[] = [];
  const hasNoCells = health.reasons.includes('no_cells');
  if (!hasNoCells && health.diff_pct !== null && health.diff_pct !== 0) {
    const isNegative = health.diff_eur?.startsWith('-') ?? false;
    const direction = isNegative ? 'under' : 'over';
    parts.push(`Cells ${Math.abs(health.diff_pct).toFixed(1)}% ${direction} budget`);
  }
  for (const r of health.reasons) {
    if (hasNoCells && r === 'value_divergence') continue;
    const label = HEALTH_REASON_LABELS[r];
    if (label && !parts.includes(label)) parts.push(label);
  }
  return parts.join(' • ');
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
  const title = healthTooltip(health) || health.status;
  return (
    <Icon
      data-testid={testId}
      className={`h-3.5 w-3.5 shrink-0 ${colorClass}`}
      aria-label={title}
    >
      <title>{title}</title>
    </Icon>
  );
}

function ProjectNameCellRenderer({ project }: { readonly project: AccrualGridProject }): JSX.Element {
  return (
    <span className="flex items-center gap-1.5 min-w-0">
      <HealthIndicator health={project.health} />
      <Link
        to={`/tracker/projects/${project.id}`}
        className="block min-w-0 truncate text-sm hover:underline"
        title={project.name}
      >
        {project.name}
      </Link>
    </span>
  );
}

function diffBadgeClass(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 5) return 'text-emerald-700';
  if (abs <= 20) return 'text-amber-600';
  return 'text-red-600';
}

function BudgetEurCellRenderer({ project }: { readonly project: AccrualGridProject }): JSX.Element {
  const { diff_pct, diff_eur } = project.health;
  const isNegative = diff_eur?.startsWith('-') ?? false;
  return (
    <span className="flex items-baseline gap-1 text-xs tabular-nums">
      <span>{formatAmount(project.budget_eur)}</span>
      {diff_pct !== null && Math.abs(diff_pct) > 0.5 ? (
        <span className={`${diffBadgeClass(diff_pct)} text-[10px]`}>
          {isNegative ? '−' : '+'}
          {Math.abs(diff_pct).toFixed(0)}%
        </span>
      ) : null}
    </span>
  );
}

function StatusDotCellRenderer({ project }: { readonly project: AccrualGridProject }): JSX.Element {
  return (
    <span className="flex items-center gap-1.5 text-xs text-foreground">
      <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${statusDotClass(project.status)}`} />
      {getStatusLabel(project.status)}
    </span>
  );
}

// Index cells by `${project_id}:${year}:${month}` so every render does
// constant-time lookup instead of scanning the cells array per cell × project.
function indexCells(cells: AccrualCellType[]): Map<string, AccrualCellType> {
  const map = new Map<string, AccrualCellType>();
  for (const c of cells) {
    map.set(buildCellKey(c.project_id, c.year, c.month), c);
  }
  return map;
}

export function buildColumns(
  months: AccrualGridMonth[],
  cells: AccrualCellType[],
  onCellChange: (projectId: string, year: number, month: number, amount: string) => void,
  canEdit: boolean,
  failedCells: ReadonlySet<string> | undefined,
): ColumnDef<AccrualGridProject>[] {
  const cellIndex = indexCells(cells);
  const sticky: ColumnDef<AccrualGridProject>[] = [
    {
      id: 'code',
      header: 'Code',
      size: 60,
      cell: ({ row }) => <ProjectCodeCellRenderer project={row.original} />,
    },
    {
      id: 'name',
      header: 'Name',
      size: 200,
      cell: ({ row }) => <ProjectNameCellRenderer project={row.original} />,
    },
    {
      id: 'status',
      header: 'Status',
      size: 80,
      cell: ({ row }) => <StatusDotCellRenderer project={row.original} />,
    },
    {
      id: 'currency',
      header: 'CCY',
      size: 70,
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{row.original.currency ?? '—'}</span>
      ),
    },
    {
      id: 'budget',
      header: 'Budget',
      size: 130,
      cell: ({ row }) => {
        const project = row.original;
        return (
          <span className="text-xs tabular-nums">
            {formatAmount(project.original_budget)}
            {project.original_budget && project.currency ? (
              <span className="ml-1 text-muted-foreground">{project.currency}</span>
            ) : null}
          </span>
        );
      },
    },
    {
      id: 'budget_eur',
      header: 'Budget €',
      size: 110,
      cell: ({ row }) => <BudgetEurCellRenderer project={row.original} />,
    },
  ];

  const monthCols: ColumnDef<AccrualGridProject>[] = months.map((m) => ({
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
      const project = row.original;
      const key = buildCellKey(project.id, m.year, m.month);
      const cell = cellIndex.get(key);
      return (
        <AccrualCell
          amount={cell?.amount ?? '0'}
          eurAmount={cell?.frozen_eur_amount ?? cell?.eur_amount ?? null}
          isOverride={cell?.is_manual_override ?? false}
          isFrozen={cell?.is_frozen ?? false}
          canEdit={canEdit}
          onChange={(newAmount) => onCellChange(project.id, m.year, m.month, newAmount)}
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
  projects: AccrualGridProject[],
  cells: AccrualCellType[],
): Map<string, number> {
  const cellIndex = indexCells(cells);
  const result = new Map<string, number>();
  for (const m of months) {
    let total = 0;
    for (const p of projects) {
      const cell = cellIndex.get(buildCellKey(p.id, m.year, m.month));
      if (cell) total += resolveEurAmount(cell);
    }
    result.set(`${m.year}_${m.month}`, total);
  }
  return result;
}
