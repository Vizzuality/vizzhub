import { cn } from '@/lib/utils';
import EditableMetricCard, { type HistoricalDataPoint } from './EditableMetricCard';
import { KPIDisplay } from './IndicatorDisplay';

interface GovernanceCardProps {
  value: number | null | undefined;
  target: number | null;
  onSave: (value: number) => Promise<unknown>;
  isPending: boolean;
  historicalData?: HistoricalDataPoint[];
}

export default function GovernanceCard({
  value,
  target,
  onSave,
  isPending,
  historicalData,
}: GovernanceCardProps): JSX.Element {
  return (
    <EditableMetricCard<number>
      historicalData={historicalData}
      title="Governance Compliance"
      description="Exceptions from latest peer review"
      tooltipContent={<p className="font-mono text-xs">score = 1 - (exceptions / target)</p>}
      data={value}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={0}
      editButtonLabel={value !== undefined && value !== null ? 'Edit Exceptions' : 'Add Exceptions'}
      renderEditForm={(form, setForm) => (
        <div>
          <label className="text-sm font-medium text-muted-foreground">
            Number of unjustified exceptions
          </label>
          <input
            type="number"
            min="0"
            value={form}
            onChange={(e) => setForm(parseInt(e.target.value) || 0)}
            className="mt-1 w-full px-3 py-2 border rounded-md bg-background"
            placeholder="0"
          />
        </div>
      )}
      renderDisplay={(data) => (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Exceptions count</span>
            <span
              className={cn(
                'text-3xl font-bold',
                data === undefined || data === null || target === null
                  ? 'text-muted-foreground'
                  : data < target
                  ? 'text-score-green'
                  : data === target
                  ? 'text-score-yellow'
                  : 'text-score-red'
              )}
            >
              {data ?? '—'}
            </span>
          </div>
          <KPIDisplay
            target={target}
            format="count"
            comparison="lte"
            unit="exceptions"
          />
        </>
      )}
    />
  );
}
