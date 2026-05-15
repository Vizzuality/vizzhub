import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import EditableMetricCard, { type HistoricalDataPoint } from './EditableMetricCard';
import { IndicatorScoreDisplay, KPIDisplay } from './IndicatorDisplay';
import type { Architecture } from '../../types';

const CHECKLIST_ITEMS = [
  {
    key: 'docs_up_to_date',
    label: 'Architecture documentation is up to date',
    description: 'The overall structure of the system is clearly defined and reflects current implementation',
    shortLabel: 'Docs up to date',
  },
  {
    key: 'iac_implemented',
    label: 'Infrastructure as Code implemented',
    description: 'All infrastructure is reproducible through code, ensuring consistency and version control',
    shortLabel: 'IaC implemented',
  },
  {
    key: 'adrs_maintained',
    label: 'Architecture Decision Records maintained',
    description: 'Important technical decisions and their rationale are recorded',
    shortLabel: 'ADRs maintained',
  },
  {
    key: 'diagrams_updated',
    label: 'System/dependency diagrams updated',
    description: 'Relationships between services and modules are documented accurately',
    shortLabel: 'Diagrams updated',
  },
] as const;

type ChecklistKey = (typeof CHECKLIST_ITEMS)[number]['key'];

interface ArchitectureCardProps {
  data: Architecture | null | undefined;
  indicatorValue: number | null;
  target: number | null;
  onSave: (data: Record<ChecklistKey, boolean>) => Promise<unknown>;
  isPending: boolean;
  historicalData?: HistoricalDataPoint[];
  editable?: boolean;
}

const DEFAULT_FORM: Record<ChecklistKey, boolean> = {
  docs_up_to_date: false,
  iac_implemented: false,
  adrs_maintained: false,
  diagrams_updated: false,
};

export default function ArchitectureCard({
  data,
  indicatorValue,
  target,
  onSave,
  isPending,
  historicalData,
  editable = true,
}: ArchitectureCardProps): JSX.Element {
  return (
    <EditableMetricCard<Record<ChecklistKey, boolean>>
      historicalData={historicalData}
      dimension="Engineering"
      title="Architecture Checklist"
      description="Documentation & infrastructure practices"
      tooltipContent={<p className="font-mono text-xs">score = yes_count / 4</p>}
      indicatorValue={indicatorValue}
      target={target}
      data={data as Record<ChecklistKey, boolean> | null | undefined}
      onSave={onSave}
      isPending={isPending}
      disabled={!editable}
      defaultFormState={DEFAULT_FORM}
      editButtonLabel={data ? 'Edit Checklist' : 'Add Checklist'}
      renderEditForm={(form, setForm) => {
        const handleChecklistChange = (itemKey: ChecklistKey, value: boolean): void => {
          setForm((prev) => ({ ...prev, [itemKey]: value }));
        };
        return (
          <>
            {CHECKLIST_ITEMS.map(({ key, label, description }) => (
              <div key={key}>
                <label className="text-sm font-medium text-muted-foreground">{label}</label>
                <p className="text-xs text-muted-foreground mb-2">{description}</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={form[key] === true ? 'default' : 'outline'}
                    onClick={() => handleChecklistChange(key, true)}
                    className="flex-1"
                  >
                    Yes
                  </Button>
                  <Button
                    size="sm"
                    variant={form[key] === false ? 'default' : 'outline'}
                    onClick={() => handleChecklistChange(key, false)}
                    className="flex-1"
                  >
                    No
                  </Button>
                </div>
              </div>
            ))}
          </>
        );
      }}
      renderDisplay={(displayData) => (
        <>
          <IndicatorScoreDisplay
            label="Score"
            indicatorValue={indicatorValue}
            target={target}
          />
          <KPIDisplay target={target} />
          {displayData && (
            <div className="space-y-1 pt-2 border-t border-border/50">
              {CHECKLIST_ITEMS.map(({ key, shortLabel }) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{shortLabel}</span>
                  <span className="flex items-center gap-1">
                    <span className={cn('inline-block w-1.5 h-1.5 rounded-full shrink-0', displayData[key] ? 'bg-aux-neon-grass' : 'bg-aux-red')} />
                    {displayData[key] ? 'Yes' : 'No'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    />
  );
}
