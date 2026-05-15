import { Link } from 'react-router-dom';
import { Pencil, BellOff } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import SubIndicatorCard from '../SubIndicatorCard';
import { EVMDataGrid } from './EVM';
import { getHistoricalData } from '@/utils/chartUtils';
import { calculateEVMValues, formatCurrency, getPerformanceLabel } from '@/shared/utils/evmCalculations';
import type { EVMData, Milestone, Indicators, MetricsWithScores, Dimension } from '../../types';

interface EVMSectionProps {
  readonly projectId: string;
  readonly evmData?: EVMData | null;
  readonly milestones?: Milestone[] | null;
  readonly indicators: Indicators;
  readonly getTarget: (name: string) => number | null;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
  readonly currency?: string;
  readonly budgetAlertsEnabled?: boolean;
}

function BudgetAlertsOffBadge(): JSX.Element {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid="alerts-off-badge"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted text-xs font-medium text-muted-foreground cursor-help"
          >
            <BellOff className="h-3 w-3" />
            Alerts off
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs max-w-xs">
            Budget Slack alerting is disabled in project settings. The CPI score reflects collected
            EVM data; only the alert workflow is muted.
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function isDimensionVisible(visibleDimensions: Set<Dimension> | undefined, dimension: Dimension): boolean {
  if (!visibleDimensions) return true;
  return visibleDimensions.has(dimension);
}

export default function EVMSection({
  projectId,
  evmData,
  milestones,
  indicators,
  getTarget,
  snapshots,
  visibleDimensions,
  currency,
  budgetAlertsEnabled = true,
}: EVMSectionProps): JSX.Element {
  const showTime = isDimensionVisible(visibleDimensions, 'Time');
  const showCost = isDimensionVisible(visibleDimensions, 'Cost');

  const milestonesTarget = (getTarget('target_milestones_on_time') ?? 85) / 100;
  const spiTarget = getTarget('target_spi') ?? 0.8;
  const cpiTarget = getTarget('target_cpi') ?? 0.8;

  const evmValues = evmData
    ? calculateEVMValues(evmData.budget_total, evmData.cost_to_date, evmData.percent_completed, evmData.percent_planned)
    : null;
  const spiValue = evmValues?.spi ?? null;
  const cpiValue = evmValues?.cpi ?? null;
  const earnedValue = evmValues?.ev ?? null;

  return (
    <>
      <Separator className="my-6" />
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">Budget & Schedule</h2>
          {!evmData && (
            <Button variant="ghost" size="sm" className="border border-input" asChild>
              <Link to={`/projects/${projectId}/edit`}>
                <Pencil className="w-4 h-4 mr-2" />
                Add Budget Data
              </Link>
            </Button>
          )}
        </div>

        {/* EVM Data Card */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            {evmData ? (
              <EVMDataGrid evmData={evmData} currency={currency} />
            ) : (
              <p className="text-muted-foreground">
                No budget data available. Click &quot;Add Budget Data&quot; to enter budget and
                schedule information.
              </p>
            )}
          </CardContent>
        </Card>


        {/* Performance Indicators Grid */}
        {evmData && (showTime || showCost) && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {showCost && (
              <SubIndicatorCard
                title="Cost Performance (CPI)"
                dimension="Cost"
                indicatorValue={cpiValue === null ? null : cpiValue * 100}
                indicatorLabel="Earned Value / Actual Cost"
                indicatorSuffix="%"
                description={cpiValue === null ? undefined : getPerformanceLabel(cpiValue, 'cpi')}
                target={cpiTarget * 100}
                lowerIsBetter={false}
                formula="EV / Cost to Date"
                metrics={[
                  { label: 'Earned Value', value: earnedValue === null ? '-' : formatCurrency(earnedValue, currency) },
                  { label: 'Cost to Date', value: formatCurrency(evmData.cost_to_date, currency) },
                ]}
                historicalData={getHistoricalData(snapshots, 'cpi', 100)}
                badge={!budgetAlertsEnabled ? <BudgetAlertsOffBadge /> : undefined}
              />
            )}

            {showTime && (
              <SubIndicatorCard
                title="Schedule Performance (SPI)"
                dimension="Time"
                indicatorValue={spiValue === null ? null : spiValue * 100}
                indicatorLabel="Work Completed / Expected"
                indicatorSuffix="%"
                description={spiValue === null ? undefined : getPerformanceLabel(spiValue, 'spi')}
                target={spiTarget * 100}
                lowerIsBetter={false}
                formula="% Completed / % Planned"
                metrics={[
                  { label: 'Completed', value: `${(evmData.percent_completed * 100).toFixed(0)}%` },
                  { label: 'Planned', value: `${(evmData.percent_planned * 100).toFixed(0)}%` },
                ]}
                historicalData={getHistoricalData(snapshots, 'spi', 100)}
              />
            )}

            {showTime && (
              <SubIndicatorCard
                title="On-Time Milestones"
                dimension="Time"
                indicatorValue={indicators.on_time_milestones === null ? null : indicators.on_time_milestones * 100}
                indicatorLabel="Delivery rate"
                indicatorSuffix="%"
                description="Milestones delivered within grace period"
                target={milestonesTarget * 100}
                lowerIsBetter={false}
                formula="on_time / total"
                metrics={[
                  { label: 'Total Milestones', value: milestones?.length ?? 0 },
                ]}
                historicalData={getHistoricalData(snapshots, 'on_time_milestones', 100)}
              />
            )}
          </div>
        )}

      </div>
    </>
  );
}
