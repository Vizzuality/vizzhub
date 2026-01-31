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

export default function StrategicImpactCard({
  value,
  onSave,
  isPending,
}: StrategicImpactCardProps): JSX.Element {
  return (
    <EditableMetricCard<StrategicImpact>
      title="Strategic Impact"
      description="Business value delivered by the project"
      tooltipContent={<p className="font-mono text-xs">Low=25, Medium=55, High=80, Transformational=100</p>}
      data={value}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={'low' as StrategicImpact}
      editButtonLabel={value ? 'Edit Strategic Impact' : 'Set Strategic Impact'}
      renderEditForm={(form, setForm) => (
        <div className="space-y-3">
          <label className="text-sm font-medium text-muted-foreground">
            Select strategic impact level
          </label>
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
      )}
      renderDisplay={(data) => (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Impact Level</span>
            <span
              className={cn(
                'text-2xl font-bold capitalize',
                !data
                  ? 'text-muted-foreground'
                  : data === 'transformational'
                  ? 'text-score-green'
                  : data === 'high'
                  ? 'text-blue-600 dark:text-blue-400'
                  : data === 'medium'
                  ? 'text-score-yellow'
                  : 'text-orange-600 dark:text-orange-400'
              )}
            >
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
