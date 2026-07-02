import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useClientLeaderboard, useProjectLeaderboard } from '../hooks/usePortfolioDashboard';
import { LeaderboardBarChart, type BarDatum } from '../components/LeaderboardBarChart';
import { ClientTable, ProjectTable } from '../components/LeaderboardTable';
import type { ClientRow, ProjectRow } from '../types/portfolio';

const ALL = 'all';
const TOP_N = 10;
type Metric = 'profit_eur' | 'margin_pct' | 'delay_months';

export default function PortfolioDashboard(): JSX.Element {
  const { state, setState } = useUrlState({
    year: { defaultValue: ALL },
    group: { defaultValue: 'project' },
    metric: { defaultValue: 'profit_eur' },
    dir: { defaultValue: 'desc' },
  });
  const [expanded, setExpanded] = useState(false);
  const year = state.year === ALL ? undefined : Number.parseInt(state.year, 10);
  const isClient = state.group === 'client';
  const metric = state.metric as Metric;
  const dir = state.dir as 'asc' | 'desc';

  const projectBoard = useProjectLeaderboard(year);
  const clientBoard = useClientLeaderboard(year);
  const board = isClient ? clientBoard : projectBoard;

  if (board.isLoading && !board.data) return <LoadingSpinner />;
  if (!board.data) return <p className="text-muted-foreground text-sm">No data</p>;

  const years = board.data.available_years;
  const idx = year === undefined ? -1 : years.indexOf(year);
  const rows = [...board.data.rows] as (ProjectRow | ClientRow)[];
  rows.sort((a, b) => {
    const nullSentinel = dir === 'desc' ? -Infinity : Infinity;
    const av = (a[metric] ?? nullSentinel) as number;
    const bv = (b[metric] ?? nullSentinel) as number;
    return dir === 'desc' ? bv - av : av - bv;
  });
  const shown = expanded ? rows : rows.slice(0, TOP_N);
  const isCurrency = metric === 'profit_eur';
  const bars: BarDatum[] = rows.slice(0, TOP_N).map((r) => ({
    label: isClient ? (r as ClientRow).client_name : (r as ProjectRow).name,
    value: (r[metric] ?? 0) as number,
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Button variant={state.year === ALL ? 'default' : 'outline'} size="sm"
                  onClick={() => setState({ year: ALL })}>All time</Button>
          {year !== undefined && (
            <>
              <Button variant="outline" size="sm" disabled={idx <= 0}
                      onClick={() => setState({ year: String(years[idx - 1]) })}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm tabular-nums w-12 text-center">{year}</span>
              <Button variant="outline" size="sm" disabled={idx < 0 || idx >= years.length - 1}
                      onClick={() => setState({ year: String(years[idx + 1]) })}>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </>
          )}
          {state.year === ALL && years.length > 0 && (
            <Button variant="outline" size="sm"
                    onClick={() => setState({ year: String(years[years.length - 1]) })}>
              Latest year
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant={!isClient ? 'default' : 'outline'} size="sm"
                  onClick={() => setState({ group: 'project' })}>Project</Button>
          <Button variant={isClient ? 'default' : 'outline'} size="sm"
                  onClick={() => setState({ group: 'client' })}>Client</Button>
        </div>
        <div className="flex items-center gap-2">
          {(['profit_eur', 'margin_pct', 'delay_months'] as Metric[]).map((m) => (
            <Button key={m} variant={metric === m ? 'default' : 'outline'} size="sm"
                    onClick={() => setState({ metric: m })}>
              {m === 'profit_eur' ? 'Profit €' : m === 'margin_pct' ? 'Margin %' : 'Delay'}
            </Button>
          ))}
          <Button variant="outline" size="sm"
                  onClick={() => setState({ dir: dir === 'desc' ? 'asc' : 'desc' })}>
            {dir === 'desc' ? '↓' : '↑'}
          </Button>
          <span className="text-xs text-muted-foreground">{rows.length} rows</span>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">No finished projects in this period</p>
      ) : (
        <>
          <LeaderboardBarChart data={bars} isCurrency={isCurrency} />
          {isClient
            ? <ClientTable rows={shown as ClientRow[]} />
            : <ProjectTable rows={shown as ProjectRow[]} />}
          {rows.length > TOP_N && (
            <Button variant="ghost" size="sm" onClick={() => setExpanded((e) => !e)}>
              {expanded ? 'Show less' : `Show more (${rows.length - TOP_N})`}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
