import { useState } from 'react';
import { Pencil, Info, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Clock, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import EVMForm from '../Forms/EVMForm';
import MilestonesForm from '../Forms/MilestonesForm';
import type { EVMData, Milestone, Indicators } from '../../types';

interface EVMSectionProps {
  evmData?: EVMData | null;
  milestones?: Milestone[] | null;
  indicators: Indicators;
  onUpdateEVM: (data: EVMData) => Promise<void>;
  onUpdateMilestones: (data: Milestone[]) => Promise<void>;
  isUpdatingEVM: boolean;
  isUpdatingMilestones: boolean;
  getTarget: (name: string) => number | null;
  getConstant: (name: string) => number | null;
}

export default function EVMSection({
  evmData,
  milestones,
  indicators,
  onUpdateEVM,
  onUpdateMilestones,
  isUpdatingEVM,
  isUpdatingMilestones,
  getTarget,
  getConstant,
}: EVMSectionProps): JSX.Element {
  const [isEditingEVM, setIsEditingEVM] = useState(false);
  const [isEditingMilestones, setIsEditingMilestones] = useState(false);
  const [showMilestones, setShowMilestones] = useState(false);

  const handleUpdateEVM = async (data: EVMData): Promise<void> => {
    await onUpdateEVM(data);
    setIsEditingEVM(false);
  };

  const handleUpdateMilestones = async (data: Milestone[]): Promise<void> => {
    await onUpdateMilestones(data);
    setIsEditingMilestones(false);
  };

  const handleDeleteMilestone = async (index: number): Promise<void> => {
    if (!milestones) return;
    const updated = milestones.filter((_, i) => i !== index);
    await onUpdateMilestones(updated);
  };

  const getMilestoneStatus = (milestone: Milestone): 'on-time' | 'late' | 'pending' => {
    const today = new Date();
    const planned = new Date(milestone.planned_date);
    const graceDays = getConstant('const_grace_days') ?? 3;
    const graceDate = new Date(planned);
    graceDate.setDate(graceDate.getDate() + graceDays);

    if (milestone.actual_date) {
      const actual = new Date(milestone.actual_date);
      return actual <= graceDate ? 'on-time' : 'late';
    }
    return today > graceDate ? 'late' : 'pending';
  };

  return (
    <>
      <Separator className="my-6" />
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-semibold">Budget & Schedule</h2>
          {!isEditingEVM && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditingEVM(true)}
              className="border border-input"
            >
              <Pencil className="w-4 h-4 mr-2" />
              {evmData ? 'Edit' : 'Add EVM Data'}
            </Button>
          )}
        </div>
        <Card>
          <CardContent className="pt-6">
            {isEditingEVM ? (
              <EVMForm
                initialData={evmData ?? undefined}
                onSubmit={handleUpdateEVM}
                onCancel={() => setIsEditingEVM(false)}
                isLoading={isUpdatingEVM}
              />
            ) : evmData ? (
              <div className="space-y-4">
                {/* Input Values */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-muted rounded-lg">
                    <p className="text-sm text-muted-foreground">Total Budget</p>
                    <p className="text-2xl font-semibold">
                      ${evmData.budget_total.toLocaleString()}
                    </p>
                  </div>
                  <div className="p-4 bg-muted rounded-lg">
                    <p className="text-sm text-muted-foreground">Actual Cost</p>
                    <p className="text-2xl font-semibold">
                      ${evmData.cost_to_date.toLocaleString()}
                    </p>
                  </div>
                  <div className="p-4 bg-muted rounded-lg">
                    <p className="text-sm text-muted-foreground">Work Completed</p>
                    <p className="text-2xl font-semibold">
                      {(evmData.percent_completed * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="p-4 bg-muted rounded-lg">
                    <p className="text-sm text-muted-foreground">Expected Progress</p>
                    <p className="text-2xl font-semibold">
                      {(evmData.percent_planned * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                {/* Calculated Values + Milestones */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <EVCard label="Earned Value (EV)" tooltip="Budget × Work Completed">
                    <p className="text-xl font-semibold">
                      $
                      {(evmData.budget_total * evmData.percent_completed).toLocaleString(
                        undefined,
                        { maximumFractionDigits: 0 }
                      )}
                    </p>
                  </EVCard>

                  <SPICard evmData={evmData} getTarget={getTarget} />
                  <CPICard evmData={evmData} getTarget={getTarget} />

                  {/* Milestones Card */}
                  <button
                    onClick={() => setShowMilestones(!showMilestones)}
                    className="p-4 bg-muted/50 rounded-lg border text-left hover:bg-muted/70 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-muted-foreground">On-Time Milestones</p>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-muted-foreground">
                                <Info className="h-3 w-3" />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-sm">On-time delivery rate</p>
                              <p className="text-xs text-white/70 mt-1">Target: 85%</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                      {showMilestones ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                    {indicators.on_time_milestones !== null ? (
                      (() => {
                        const milestonesTarget = (getTarget('target_milestones_on_time') ?? 85) / 100;
                        return (
                          <>
                            <p
                              className={cn(
                                'text-xl font-semibold',
                                indicators.on_time_milestones >= milestonesTarget
                                  ? 'text-score-green'
                                  : indicators.on_time_milestones >= milestonesTarget * 0.9
                                  ? 'text-score-yellow'
                                  : 'text-score-red'
                              )}
                            >
                              {(indicators.on_time_milestones * 100).toFixed(0)}%
                            </p>
                            <div className="flex justify-between items-center">
                              <p className="text-xs text-muted-foreground">
                                {milestones?.length || 0} milestone
                                {(milestones?.length || 0) !== 1 ? 's' : ''}
                              </p>
                              <p className="text-xs text-chart-3">expand to edit</p>
                            </div>
                          </>
                        );
                      })()
                    ) : (
                      <>
                        <p className="text-xl font-semibold text-muted-foreground">—</p>
                        <div className="flex justify-between items-center">
                          <p className="text-xs text-muted-foreground">No milestones</p>
                          <p className="text-xs text-chart-3">expand to edit</p>
                        </div>
                      </>
                    )}
                  </button>
                </div>

                {/* Expanded Milestones List */}
                {showMilestones && (
                  <div className="mt-4">
                    {isEditingMilestones ? (
                      <MilestonesForm
                        initialData={milestones ?? undefined}
                        onSubmit={handleUpdateMilestones}
                        onCancel={() => setIsEditingMilestones(false)}
                        isLoading={isUpdatingMilestones}
                      />
                    ) : (
                      <>
                        {milestones && milestones.length > 0 ? (
                          <div className="space-y-2">
                            {milestones.map((milestone, index) => {
                              const status = getMilestoneStatus(milestone);
                              return (
                                <div
                                  key={index}
                                  className="flex items-center justify-between p-3 bg-muted/50 rounded-lg group"
                                >
                                  <div className="flex items-center gap-3">
                                    {status === 'on-time' && (
                                      <CheckCircle2 className="w-5 h-5 text-score-green" />
                                    )}
                                    {status === 'late' && (
                                      <AlertCircle className="w-5 h-5 text-score-red" />
                                    )}
                                    {status === 'pending' && (
                                      <Clock className="w-5 h-5 text-muted-foreground" />
                                    )}
                                    <span className="font-medium">{milestone.name}</span>
                                  </div>
                                  <div className="flex items-center gap-4 text-sm">
                                    <span className="text-muted-foreground">
                                      Planned:{' '}
                                      {new Date(milestone.planned_date).toLocaleDateString()}
                                    </span>
                                    <span
                                      className={cn(
                                        milestone.actual_date
                                          ? status === 'on-time'
                                            ? 'text-score-green'
                                            : 'text-score-red'
                                          : status === 'pending'
                                          ? 'text-score-green'
                                          : 'text-score-red'
                                      )}
                                    >
                                      Actual:{' '}
                                      {milestone.actual_date
                                        ? new Date(milestone.actual_date).toLocaleDateString()
                                        : '--/--/----'}
                                    </span>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                                      onClick={() => handleDeleteMilestone(index)}
                                      disabled={isUpdatingMilestones}
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-muted-foreground">No milestones defined yet.</p>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setIsEditingMilestones(true)}
                          className="mt-4 border border-input"
                        >
                          <Pencil className="w-4 h-4 mr-2" />
                          {milestones?.length ? 'Edit Milestones' : 'Add Milestones'}
                        </Button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">
                No budget data available. Click "Add EVM Data" to enter budget and schedule
                information.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function EVCard({
  label,
  tooltip,
  children,
}: {
  label: string;
  tooltip: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center gap-2 mb-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="text-muted-foreground">
                <Info className="h-3 w-3" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              <p className="text-sm">{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      {children}
    </div>
  );
}

function SPICard({
  evmData,
  getTarget,
}: {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
}): JSX.Element {
  const spiTarget = getTarget('target_spi') ?? 0.8;

  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">Schedule Performance (SPI)</p>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-muted-foreground">
                  <Info className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-sm">Work Completed / Expected Progress</p>
                <p className="text-xs text-white/70 mt-1">
                  &gt;1 = ahead, 1 = on track, &lt;1 = behind
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <span className="text-sm text-foreground">≥{(spiTarget * 100).toFixed(0)}%</span>
      </div>
      {evmData.percent_planned > 0 ? (
        (() => {
          const spi = evmData.percent_completed / evmData.percent_planned;
          return (
            <>
              <p
                className={cn(
                  'text-xl font-semibold',
                  spi >= spiTarget
                    ? 'text-score-green'
                    : spi >= spiTarget * 0.9
                    ? 'text-score-yellow'
                    : 'text-score-red'
                )}
              >
                {(spi * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-muted-foreground">
                {spi > 1 ? 'Ahead of schedule' : spi === 1 ? 'On schedule' : 'Behind schedule'}
              </p>
            </>
          );
        })()
      ) : (
        <p className="text-xl font-semibold text-muted-foreground">—</p>
      )}
    </div>
  );
}

function CPICard({
  evmData,
  getTarget,
}: {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
}): JSX.Element {
  const cpiTarget = getTarget('target_cpi') ?? 0.8;

  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">Cost Performance (CPI)</p>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-muted-foreground">
                  <Info className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-sm">Earned Value / Actual Cost</p>
                <p className="text-xs text-white/70 mt-1">
                  &gt;1 = under budget, 1 = on budget, &lt;1 = over budget
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <span className="text-sm text-foreground">≥{(cpiTarget * 100).toFixed(0)}%</span>
      </div>
      {evmData.cost_to_date > 0 ? (
        (() => {
          const cpi =
            (evmData.budget_total * evmData.percent_completed) / evmData.cost_to_date;
          return (
            <>
              <p
                className={cn(
                  'text-xl font-semibold',
                  cpi >= cpiTarget
                    ? 'text-score-green'
                    : cpi >= cpiTarget * 0.9
                    ? 'text-score-yellow'
                    : 'text-score-red'
                )}
              >
                {(cpi * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-muted-foreground">
                {cpi > 1 ? 'Under budget' : cpi === 1 ? 'On budget' : 'Over budget'}
              </p>
            </>
          );
        })()
      ) : (
        <p className="text-xl font-semibold text-muted-foreground">—</p>
      )}
    </div>
  );
}
