import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { usePortfolioDashboard } from '../hooks/usePortfolioDashboard';
import { DashboardKpis } from '../components/DashboardKpis';
import { VolumeByYearChart } from '../components/VolumeByYearChart';
import { SpendByClientChart } from '../components/SpendByClientChart';
import { MarginSplitChart } from '../components/MarginSplitChart';
import { TermBreakdownChart } from '../components/TermBreakdownChart';

const ALL = 'all';

export default function PortfolioDashboard(): JSX.Element {
  const { state, setState } = useUrlState({ year: { defaultValue: ALL } });
  const year = state.year === ALL ? undefined : Number.parseInt(state.year, 10);
  const { data, isLoading } = usePortfolioDashboard(year);

  if (isLoading && !data) return <LoadingSpinner />;
  if (!data) return <p className="text-muted-foreground text-sm">No data</p>;

  const years = data.available_years;
  const idx = year === undefined ? -1 : years.indexOf(year);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            variant={state.year === ALL ? 'default' : 'outline'}
            size="sm"
            onClick={() => setState({ year: ALL })}
          >
            All time
          </Button>
          {year !== undefined && (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={idx <= 0}
                onClick={() => setState({ year: String(years[idx - 1]) })}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm tabular-nums w-12 text-center">{year}</span>
              <Button
                variant="outline"
                size="sm"
                disabled={idx < 0 || idx >= years.length - 1}
                onClick={() => setState({ year: String(years[idx + 1]) })}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </>
          )}
          {state.year === ALL && years.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setState({ year: String(years[years.length - 1]) })}
            >
              Latest year
            </Button>
          )}
        </div>
      </div>

      <DashboardKpis kpis={data.kpis} />

      <div className="grid gap-4 lg:grid-cols-2">
        <VolumeByYearChart data={data.volume_by_year} />
        <MarginSplitChart data={data.margin_split} />
        <SpendByClientChart data={data.spend_by_client} />
        {data.breakdowns.map((b) => (
          <TermBreakdownChart key={b.taxonomy_slug} data={b} />
        ))}
      </div>
    </div>
  );
}
