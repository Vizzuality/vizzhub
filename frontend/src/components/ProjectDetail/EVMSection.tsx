import { useState } from 'react';
import { Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import EVMForm from '../Forms/EVMForm';
import { EVCard, SPICard, CPICard, EVMDataGrid, MilestonesCard, MilestonesList } from './EVM';
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

type MilestoneStatus = 'on-time' | 'late' | 'pending';

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

  const getMilestoneStatus = (milestone: Milestone): MilestoneStatus => {
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

  const milestonesTarget = (getTarget('target_milestones_on_time') ?? 85) / 100;

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
                <EVMDataGrid evmData={evmData} />

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <EVCard label="Earned Value (EV)" tooltip="Budget x Work Completed">
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

                  <MilestonesCard
                    milestones={milestones}
                    onTimeMilestones={indicators.on_time_milestones}
                    milestonesTarget={milestonesTarget}
                    isExpanded={showMilestones}
                    onToggle={() => setShowMilestones(!showMilestones)}
                  />
                </div>

                {showMilestones && (
                  <div className="mt-4">
                    <MilestonesList
                      milestones={milestones}
                      isEditing={isEditingMilestones}
                      isLoading={isUpdatingMilestones}
                      onEdit={() => setIsEditingMilestones(true)}
                      onCancelEdit={() => setIsEditingMilestones(false)}
                      onSubmit={handleUpdateMilestones}
                      onDelete={handleDeleteMilestone}
                      getMilestoneStatus={getMilestoneStatus}
                    />
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
