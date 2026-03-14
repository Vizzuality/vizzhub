import { Link } from 'react-router-dom';
import { Pencil } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
import SubIndicatorCard from '../SubIndicatorCard';
import { EVMDataGrid, MilestonesList } from './EVM';
import { getHistoricalData } from '@/utils/chartUtils';
import type { EVMData, Milestone, Indicators, MetricsWithScores, Dimension } from '../../types';

interface EVMSectionProps {
  readonly projectId: string;
  readonly evmData?: EVMData | null;
  readonly milestones?: Milestone[] | null;
  readonly indicators: Indicators;
  readonly getTarget: (name: string) => number | null;
  readonly getConstant: (name: string) => number | null;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
}

type MilestoneStatus = 'on-time' | 'late' | 'pending';

function isDimensionVisible(visibleDimensions: Set<Dimension> | undefined, dimension: Dimension): boolean {
  if (!visibleDimensions) return true;
  return visibleDimensions.has(dimension);
}

function calculateSPI(evmData: EVMData | null | undefined): number | null {
  if (!evmData) return null;
  if (evmData.percent_planned <= 0) return null;
  return evmData.percent_completed / evmData.percent_planned;
}

function calculateCPI(evmData: EVMData | null | undefined): number | null {
  if (!evmData) return null;
  if (evmData.cost_to_date <= 0) return null;
  return (evmData.budget_total * evmData.percent_completed) / evmData.cost_to_date;
}

function calculateEarnedValue(evmData: EVMData | null | undefined): number | null {
  if (!evmData) return null;
  return evmData.budget_total * evmData.percent_completed;
}

function getSPIStatus(value: number): string {
  if (value > 1) return 'Ahead of schedule';
  if (value === 1) return 'On schedule';
  return 'Behind schedule';
}

function getCPIStatus(value: number): string {
  if (value > 1) return 'Under budget';
  if (value === 1) return 'On budget';
  return 'Over budget';
}

export default function EVMSection({
  projectId,
  evmData,
  milestones,
  indicators,
  getTarget,
  getConstant,
  snapshots,
  visibleDimensions,
}: EVMSectionProps): JSX.Element {
  const showTime = isDimensionVisible(visibleDimensions, 'Time');
  const showCost = isDimensionVisible(visibleDimensions, 'Cost');

  const getMilestoneStatus = (milestone: Milestone): MilestoneStatus => {
    const today = new Date();
    const planned = new Date(milestone.planned_date);
    const graceDays = getConstant('const_grace_days') ?? 3;
    const graceDate = new Date(planned);
    graceDate.setDate(graceDate.getDate() + graceDays);

    if (!milestone.actual_date) {
      return today > graceDate ? 'late' : 'pending';
    }
    const actual = new Date(milestone.actual_date);
    return actual <= graceDate ? 'on-time' : 'late';
  };

  const milestonesTarget = (getTarget('target_milestones_on_time') ?? 85) / 100;
  const spiTarget = getTarget('target_spi') ?? 0.8;
  const cpiTarget = getTarget('target_cpi') ?? 0.8;

  const spiValue = calculateSPI(evmData);
  const cpiValue = calculateCPI(evmData);
  const earnedValue = calculateEarnedValue(evmData);

  return (
    <>
      <Separator className="my-6" />
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">Budget & Schedule</h2>
          <Button variant="ghost" size="sm" className="border border-input" asChild>
            <Link to={`/projects/${projectId}/edit`}>
              <Pencil className="w-4 h-4 mr-2" />
              {evmData ? 'Edit' : 'Add Budget Data'}
            </Link>
          </Button>
        </div>

        {/* EVM Data Card */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            {evmData ? (
              <EVMDataGrid evmData={evmData} />
            ) : (
              <p className="text-muted-foreground">
                No budget data available. Click &quot;Add Budget Data&quot; to enter budget and
                schedule information.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Read-only Milestones */}
        {milestones && milestones.length > 0 && (
          <Card className="mb-6">
            <CardContent className="pt-6">
              <MilestonesList
                milestones={milestones}
                isEditing={false}
                isLoading={false}
                onEdit={() => {}}
                onCancelEdit={() => {}}
                onSubmit={async () => {}}
                onDelete={async () => {}}
                getMilestoneStatus={getMilestoneStatus}
              />
            </CardContent>
          </Card>
        )}

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
                description={cpiValue === null ? undefined : getCPIStatus(cpiValue)}
                target={cpiTarget * 100}
                lowerIsBetter={false}
                formula="EV / Cost to Date"
                metrics={[
                  { label: 'Earned Value', value: `$${earnedValue?.toLocaleString(undefined, { maximumFractionDigits: 0 })}` },
                  { label: 'Cost to Date', value: `$${evmData.cost_to_date.toLocaleString(undefined, { maximumFractionDigits: 0 })}` },
                ]}
                historicalData={getHistoricalData(snapshots, 'cpi', 100)}
              />
            )}

            {showTime && (
              <SubIndicatorCard
                title="Schedule Performance (SPI)"
                dimension="Time"
                indicatorValue={spiValue === null ? null : spiValue * 100}
                indicatorLabel="Work Completed / Expected"
                indicatorSuffix="%"
                description={spiValue === null ? undefined : getSPIStatus(spiValue)}
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
