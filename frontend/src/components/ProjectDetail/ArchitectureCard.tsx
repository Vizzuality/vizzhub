import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import EditableMetricCard from './EditableMetricCard';
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
  target: number;
  onSave: (data: Record<ChecklistKey, boolean>) => Promise<unknown>;
  isPending: boolean;
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
}: ArchitectureCardProps): JSX.Element {
  const targetNormalized = target / 100;

  return (
    <EditableMetricCard<Record<ChecklistKey, boolean>>
      title="Architecture Checklist"
      description="Documentation & infrastructure practices"
      tooltipContent={<p className="font-mono text-xs">score = yes_count / 4</p>}
      indicatorValue={indicatorValue}
      target={target}
      data={data as Record<ChecklistKey, boolean> | null | undefined}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={DEFAULT_FORM}
      editButtonLabel={data ? 'Edit Checklist' : 'Add Checklist'}
      renderEditForm={(form, setForm) => (
        <>
          {CHECKLIST_ITEMS.map(({ key, label, description }) => (
            <div key={key}>
              <label className="text-sm font-medium text-muted-foreground">{label}</label>
              <p className="text-xs text-muted-foreground mb-2">{description}</p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={form[key] === true ? 'default' : 'outline'}
                  onClick={() => setForm((prev) => ({ ...prev, [key]: true }))}
                  className="flex-1"
                >
                  Yes
                </Button>
                <Button
                  size="sm"
                  variant={form[key] === false ? 'default' : 'outline'}
                  onClick={() => setForm((prev) => ({ ...prev, [key]: false }))}
                  className="flex-1"
                >
                  No
                </Button>
              </div>
            </div>
          ))}
        </>
      )}
      renderDisplay={(displayData) => (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Score</span>
            <span
              className={cn(
                'text-3xl font-bold',
                indicatorValue === null
                  ? 'text-muted-foreground'
                  : indicatorValue >= targetNormalized
                  ? 'text-score-green'
                  : indicatorValue >= targetNormalized * 0.9
                  ? 'text-score-yellow'
                  : 'text-score-red'
              )}
            >
              {indicatorValue !== null ? (indicatorValue * 100).toFixed(0) + '%' : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-border/50">
            <span className="text-xs text-muted-foreground">KPI</span>
            <span className="text-sm text-foreground">≥{target}%</span>
          </div>
          {displayData && (
            <div className="space-y-1 pt-2 border-t border-border/50">
              {CHECKLIST_ITEMS.map(({ key, shortLabel }) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{shortLabel}</span>
                  <span className={displayData[key] ? 'text-score-green' : 'text-score-red'}>
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
