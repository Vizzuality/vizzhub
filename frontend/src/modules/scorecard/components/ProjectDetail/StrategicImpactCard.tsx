import { cn } from '@/lib/utils';
import EditableMetricCard from './EditableMetricCard';
import type { StrategicImpact } from '../../types';

const IMPACT_OPTIONS = [
  { value: 'low', label: 'Low', score: 25, description: 'Internal tooling, maintenance, isolated feature' },
  { value: 'medium', label: 'Medium', score: 55, description: 'Supports one team or process improvement' },
  { value: 'high', label: 'High', score: 80, description: 'Enables client delivery, product launch, or growth' },
  { value: 'transformational', label: 'Transformational', score: 100, description: 'Core strategic initiative, major partnership, innovation leap' },
] as const;

interface StrategicImpactCardProps {
  value: StrategicImpact | null | undefined;
  onSave: (value: StrategicImpact) => Promise<unknown>;
  isPending: boolean;
}

function getScoreForValue(val: StrategicImpact): number {
  const option = IMPACT_OPTIONS.find((o) => o.value === val);
  return option?.score ?? 0;
}

function getImpactDotClass(data: StrategicImpact | null | undefined): string {
  if (!data) return 'bg-aux-dust-grey';
  if (data === 'transformational') return 'bg-aux-neon-grass';
  if (data === 'high') return 'bg-blue-600';
  if (data === 'medium') return 'bg-aux-yellow';
  return 'bg-orange-600';
}

export default function StrategicImpactCard({
  value,
  onSave,
  isPending,
}: StrategicImpactCardProps): JSX.Element {
  return (
    <EditableMetricCard<StrategicImpact>
      dimension="Value"
      title="Strategic Impact"
      description="Business value delivered by the project"
      tooltipContent={<p className="font-mono text-xs">Low=25, Medium=55, High=80, Transformational=100</p>}
      data={value}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={'low' as StrategicImpact}
      editButtonLabel={value ? 'Edit Strategic Impact' : 'Set Strategic Impact'}
      renderEditForm={(form, setForm) => (
        <fieldset className="space-y-3 border-none p-0 m-0">
          <legend className="text-sm font-medium text-muted-foreground">
            Select strategic impact level
          </legend>
          <div className="space-y-3">
            {IMPACT_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setForm(option.value as StrategicImpact)}
                className={cn(
                  'w-full text-left p-3 rounded-lg border transition-colors',
                  form === option.value
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-primary/50'
                )}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium">{option.label}</span>
                  <span className="text-xs text-muted-foreground">Score: {option.score}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{option.description}</p>
              </button>
            ))}
          </div>
        </fieldset>
      )}
      renderDisplay={(data) => (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Impact Level</span>
            <span
              className={cn(
                'text-2xl font-bold capitalize text-foreground flex items-center gap-1.5',
              )}
            >
              <span className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', getImpactDotClass(data))} />
              {data ?? '—'}
            </span>
          </div>
          {data && (
            <div className="flex items-center justify-between pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground">Score contribution</span>
              <span className="text-sm font-semibold">{getScoreForValue(data)}</span>
            </div>
          )}
        </>
      )}
    />
  );
}
