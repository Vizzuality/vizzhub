import { useState, type ReactNode } from 'react';
import { ArrowDownWideNarrow, ArrowUpNarrowWide, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { ChartPagination } from '@/shared/components/ui/chart-pagination';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { SegmentedControl } from '@/shared/components/ui/segmented-control';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useClientLeaderboard, useProjectLeaderboard } from '../hooks/usePortfolioDashboard';
import { LeaderboardBarChart, type BarDatum } from '../components/LeaderboardBarChart';
import { ClientTable, ProjectTable } from '../components/LeaderboardTable';
import type { ClientRow, ProjectRow } from '../types/portfolio';
import { METRIC_CONFIG, METRIC_ORDER, type Metric, type SortDir } from '../utils/chart';

const ALL = 'all';
const TOP_N = 10;
const CHART_PAGE_SIZE = 10;

type LeaderboardRow = ProjectRow | ClientRow;

function sortLeaderboardRows(rows: LeaderboardRow[], metric: Metric, dir: SortDir): LeaderboardRow[] {
  const nullSentinel = dir === 'desc' ? -Infinity : Infinity;
  return [...rows].sort((a, b) => {
    const av = (a[metric] ?? nullSentinel) as number;
    const bv = (b[metric] ?? nullSentinel) as number;
    return dir === 'desc' ? bv - av : av - bv;
  });
}

function ControlGroup({ label, children }: { readonly label: string; readonly children: ReactNode }): JSX.Element {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

function PeriodControl({
  years,
  year,
  onChange,
}: {
  readonly years: number[];
  readonly year: number | undefined;
  readonly onChange: (year: number | undefined) => void;
}): JSX.Element {
  const isAllTime = year === undefined;
  const shownYear = year ?? years[years.length - 1];
  const shownIdx = shownYear === undefined ? -1 : years.indexOf(shownYear);
  return (
    <div className="inline-flex items-center rounded-lg bg-muted p-0.5">
      <button
        type="button"
        aria-pressed={isAllTime}
        onClick={() => onChange(undefined)}
        className={cn(
          'rounded-md px-3 py-1 text-sm font-medium transition-colors',
          isAllTime ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
        )}
      >
        All time
      </button>
      {years.length > 0 && (
        <div className={cn('flex items-center rounded-md', !isAllTime && 'bg-background shadow-sm')}>
          <button
            type="button"
            aria-label="Previous year"
            disabled={isAllTime || shownIdx <= 0}
            onClick={() => onChange(years[shownIdx - 1])}
            className="px-1.5 py-1 text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:pointer-events-none"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onChange(shownYear)}
            className={cn(
              'min-w-[3rem] px-1 py-1 text-center text-sm font-medium tabular-nums transition-colors',
              isAllTime ? 'text-muted-foreground hover:text-foreground' : 'text-foreground',
            )}
          >
            {shownYear}
          </button>
          <button
            type="button"
            aria-label="Next year"
            disabled={isAllTime || shownIdx >= years.length - 1}
            onClick={() => onChange(years[shownIdx + 1])}
            className="px-1.5 py-1 text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:pointer-events-none"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function RankByControl({
  metric,
  dir,
  onMetric,
  onDir,
}: {
  readonly metric: Metric;
  readonly dir: SortDir;
  readonly onMetric: (metric: Metric) => void;
  readonly onDir: (dir: SortDir) => void;
}): JSX.Element {
  const DirIcon = dir === 'desc' ? ArrowDownWideNarrow : ArrowUpNarrowWide;
  return (
    <div className="flex items-center gap-2">
      <SegmentedControl
        ariaLabel="Rank by metric"
        value={metric}
        onChange={onMetric}
        options={METRIC_ORDER.map((m) => ({ value: m, label: METRIC_CONFIG[m].label }))}
      />
      <button
        type="button"
        onClick={() => onDir(dir === 'desc' ? 'asc' : 'desc')}
        className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1 text-sm font-medium shadow-sm transition-colors hover:bg-muted"
      >
        <DirIcon className="w-4 h-4 text-muted-foreground" />
        {dir === 'desc' ? 'Highest first' : 'Lowest first'}
      </button>
    </div>
  );
}

// Chart + table for the current ranking. Mounted with a key that changes when the
// ranking dimensions change, so page/expand state resets to defaults on each switch.
function LeaderboardResults({
  rows,
  metric,
  dir,
  isClient,
}: {
  readonly rows: LeaderboardRow[];
  readonly metric: Metric;
  readonly dir: SortDir;
  readonly isClient: boolean;
}): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const [chartPage, setChartPage] = useState(0);

  if (rows.length === 0) {
    return <p className="text-muted-foreground text-sm">No finished projects in this period.</p>;
  }

  const allBars: BarDatum[] = rows
    .filter((r) => r[metric] != null)
    .map((r) => ({
      label: isClient ? (r as ClientRow).client_name : (r as ProjectRow).name,
      value: r[metric] as number,
    }));
  const totalPages = Math.max(1, Math.ceil(allBars.length / CHART_PAGE_SIZE));
  const safePage = Math.min(Math.max(chartPage, 0), totalPages - 1);
  const pageStart = safePage * CHART_PAGE_SIZE;
  const pageBars = allBars.slice(pageStart, pageStart + CHART_PAGE_SIZE);
  const shown = expanded ? rows : rows.slice(0, TOP_N);
  const dirLabel = dir === 'desc' ? 'highest first' : 'lowest first';
  const rangeLabel =
    allBars.length > 0 ? `#${pageStart + 1}–${pageStart + pageBars.length} of ${allBars.length}` : '—';

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium tracking-tight text-foreground">
        <span className="font-semibold">{METRIC_CONFIG[metric].label}</span>
        {` · ${rangeLabel} · ${dirLabel}`}
      </h2>
      <LeaderboardBarChart data={pageBars} metric={metric} />
      <ChartPagination data={allBars} page={safePage} onPageChange={setChartPage} pageSize={CHART_PAGE_SIZE} />
      {isClient ? <ClientTable rows={shown as ClientRow[]} /> : <ProjectTable rows={shown as ProjectRow[]} />}
      {rows.length > TOP_N && (
        <Button variant="ghost" size="sm" onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'Show less' : `Show more (${rows.length - TOP_N})`}
        </Button>
      )}
    </div>
  );
}

export default function PortfolioDashboard(): JSX.Element {
  const { state, setState } = useUrlState({
    year: { defaultValue: ALL },
    group: { defaultValue: 'project' },
    metric: { defaultValue: 'profit_eur' },
    dir: { defaultValue: 'desc' },
  });
  const year = state.year === ALL ? undefined : Number.parseInt(state.year, 10);
  const isClient = state.group === 'client';
  const metric: Metric = METRIC_ORDER.includes(state.metric as Metric)
    ? (state.metric as Metric)
    : 'profit_eur';
  const dir: SortDir = state.dir === 'asc' ? 'asc' : 'desc';

  const projectBoard = useProjectLeaderboard(year);
  const clientBoard = useClientLeaderboard(year);
  const board = isClient ? clientBoard : projectBoard;

  if (board.isLoading && !board.data) return <LoadingSpinner />;
  if (!board.data) return <p className="text-muted-foreground text-sm">No data.</p>;

  const years = board.data.available_years;
  const rows = sortLeaderboardRows(board.data.rows as LeaderboardRow[], metric, dir);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
        <ControlGroup label="View">
          <SegmentedControl
            ariaLabel="View by"
            value={state.group}
            onChange={(v) => setState({ group: v })}
            options={[
              { value: 'project', label: 'Project' },
              { value: 'client', label: 'Client' },
            ]}
          />
        </ControlGroup>

        <ControlGroup label="Period">
          <PeriodControl
            years={years}
            year={year}
            onChange={(y) => setState({ year: y === undefined ? ALL : String(y) })}
          />
        </ControlGroup>

        <ControlGroup label="Rank by">
          <RankByControl
            metric={metric}
            dir={dir}
            onMetric={(m) => setState({ metric: m })}
            onDir={(d) => setState({ dir: d })}
          />
        </ControlGroup>

        <div className="ml-auto self-end pb-1 text-sm text-muted-foreground">
          {rows.length} {isClient ? 'clients' : 'projects'}
        </div>
      </div>

      <LeaderboardResults
        key={`${metric}-${dir}-${isClient}-${year ?? 'all'}`}
        rows={rows}
        metric={metric}
        dir={dir}
        isClient={isClient}
      />
    </div>
  );
}
