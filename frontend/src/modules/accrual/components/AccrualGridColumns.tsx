import type { ColumnDef } from '@tanstack/react-table';
import { Link } from 'react-router-dom';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import { AccrualCell } from '@/modules/accrual/components/AccrualCell';
import { LockedFxRateEditor } from '@/modules/accrual/components/LockedFxRateEditor';
import { getStatusLabel } from '@/utils/projectStatus';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridMonth,
  AccrualGridProject,
} from '@/modules/accrual/types/accrual';

// Pixel offsets for each of the 7 sticky-left columns.
// code=0, name=60, status=260, currency=340, locked_fx=410, budget=510, σEUR=640
export const STICKY_LEFT_OFFSETS: readonly number[] = [0, 60, 260, 340, 410, 510, 640];

const fmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatAmount(val: string | null | undefined): string {
  if (val === null || val === undefined) return '—';
  const n = Number(val);
  return Number.isNaN(n) ? val : fmt.format(n);
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

function ProjectNameCellRenderer({ project }: { readonly project: AccrualGridProject }): JSX.Element {
  return (
    <Link
      to={`/tracker/projects/${project.id}`}
      className="block min-w-0 truncate text-sm hover:underline"
      title={project.name}
    >
      {project.name}
    </Link>
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

function MonthCellRenderer({
  project,
  year,
  month,
  cell,
  onCellChange,
  canEdit,
  hasError,
}: {
  readonly project: AccrualGridProject;
  readonly year: number;
  readonly month: number;
  readonly cell: AccrualCellType | undefined;
  readonly onCellChange: (projectId: string, year: number, month: number, amount: string) => void;
  readonly canEdit: boolean;
  readonly hasError: boolean;
}): JSX.Element {
  return (
    <AccrualCell
      amount={cell?.amount ?? '0'}
      eurAmount={cell?.frozen_eur_amount ?? cell?.eur_amount ?? null}
      isOverride={cell?.is_manual_override ?? false}
      isFrozen={cell?.is_frozen ?? false}
      canEdit={canEdit}
      onChange={(newAmount) => onCellChange(project.id, year, month, newAmount)}
      onError={hasError}
    />
  );
}

export function buildColumns(
  months: AccrualGridMonth[],
  cells: AccrualCellType[],
  onCellChange: (projectId: string, year: number, month: number, amount: string) => void,
  canEdit: boolean,
  failedCells: ReadonlySet<string> | undefined,
): ColumnDef<AccrualGridProject>[] {
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
      id: 'locked_fx_rate',
      header: 'FX',
      size: 100,
      cell: ({ row }) => (
        <LockedFxRateEditor
          projectId={row.original.id}
          projectCurrency={row.original.currency ?? ''}
          currentRate={row.original.locked_fx_rate}
          canEdit={canEdit}
        />
      ),
    },
    {
      id: 'budget',
      header: 'Budget',
      size: 130,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums">{formatAmount(row.original.budget)}</span>
      ),
    },
    {
      id: 'sigma_eur',
      header: 'Σ EUR',
      size: 110,
      cell: ({ row }) => {
        const project = row.original;
        const total = months.reduce((sum, m) => {
          const c = cells.find(
            (cell) => cell.project_id === project.id && cell.year === m.year && cell.month === m.month,
          );
          if (!c) return sum;
          const eur = c.is_frozen ? c.frozen_eur_amount : c.eur_amount;
          return sum + (Number(eur) || 0);
        }, 0);
        return <span className="text-xs tabular-nums">{fmt.format(total)}</span>;
      },
    },
  ];

  const monthCols: ColumnDef<AccrualGridProject>[] = months.map((m) => ({
    id: `month_${m.year}_${m.month}`,
    header: () => {
      const label = monthLabel(m.month);
      const showYear = m.month === 1;
      return (
        <div className="flex flex-col leading-none gap-0.5">
          {showYear && <span className="text-[10px] text-muted-foreground">{m.year}</span>}
          <span>{label}</span>
        </div>
      );
    },
    size: 90,
    meta: { year: m.year, month: m.month } satisfies MonthColumnMeta,
    cell: ({ row }) => {
      const project = row.original;
      const cell = cells.find(
        (c) => c.project_id === project.id && c.year === m.year && c.month === m.month,
      );
      const hasError = failedCells?.has(`${project.id}:${m.year}:${m.month}`) ?? false;
      return (
        <MonthCellRenderer
          project={project}
          year={m.year}
          month={m.month}
          cell={cell}
          onCellChange={onCellChange}
          canEdit={canEdit}
          hasError={hasError}
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
  const result = new Map<string, number>();
  for (const m of months) {
    let total = 0;
    for (const p of projects) {
      const cell = cells.find(
        (c) => c.project_id === p.id && c.year === m.year && c.month === m.month,
      );
      if (!cell) continue;
      const eur = cell.is_frozen ? cell.frozen_eur_amount : cell.eur_amount;
      total += Number(eur) || 0;
    }
    result.set(`${m.year}_${m.month}`, total);
  }
  return result;
}
