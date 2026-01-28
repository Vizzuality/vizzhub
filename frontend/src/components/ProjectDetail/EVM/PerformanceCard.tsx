import { cn } from '@/lib/utils';
import InfoTooltip from './InfoTooltip';
import type { EVMData } from '@/types';

interface PerformanceCardProps {
  label: string;
  tooltip: string;
  tooltipDetail: string;
  target: number;
  value: number | null;
  statusText: { above: string; equal: string; below: string };
}

export function PerformanceCard({
  label,
  tooltip,
  tooltipDetail,
  target,
  value,
  statusText,
}: PerformanceCardProps): JSX.Element {
  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">{label}</p>
          <InfoTooltip>
            <p className="text-sm">{tooltip}</p>
            <p className="text-xs text-white/70 mt-1">{tooltipDetail}</p>
          </InfoTooltip>
        </div>
        <span className="text-sm text-foreground">&ge;{(target * 100).toFixed(0)}%</span>
      </div>
      {value !== null ? (
        <>
          <p
            className={cn(
              'text-xl font-semibold',
              value >= target
                ? 'text-score-green'
                : value >= target * 0.9
                ? 'text-score-yellow'
                : 'text-score-red'
            )}
          >
            {(value * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-muted-foreground">
            {value > 1 ? statusText.above : value === 1 ? statusText.equal : statusText.below}
          </p>
        </>
      ) : (
        <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>
      )}
    </div>
  );
}

interface SPICardProps {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
}

export function SPICard({ evmData, getTarget }: SPICardProps): JSX.Element {
  const target = getTarget('target_spi') ?? 0.8;
  const value = evmData.percent_planned > 0
    ? evmData.percent_completed / evmData.percent_planned
    : null;

  return (
    <PerformanceCard
      label="Schedule Performance (SPI)"
      tooltip="Work Completed / Expected Progress"
      tooltipDetail=">1 = ahead, 1 = on track, <1 = behind"
      target={target}
      value={value}
      statusText={{ above: 'Ahead of schedule', equal: 'On schedule', below: 'Behind schedule' }}
    />
  );
}

interface CPICardProps {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
}

export function CPICard({ evmData, getTarget }: CPICardProps): JSX.Element {
  const target = getTarget('target_cpi') ?? 0.8;
  const value = evmData.cost_to_date > 0
    ? (evmData.budget_total * evmData.percent_completed) / evmData.cost_to_date
    : null;

  return (
    <PerformanceCard
      label="Cost Performance (CPI)"
      tooltip="Earned Value / Actual Cost"
      tooltipDetail=">1 = under budget, 1 = on budget, <1 = over budget"
      target={target}
      value={value}
      statusText={{ above: 'Under budget', equal: 'On budget', below: 'Over budget' }}
    />
  );
}
