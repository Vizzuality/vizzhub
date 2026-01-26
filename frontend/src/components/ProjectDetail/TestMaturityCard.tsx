import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import EditableMetricCard from './EditableMetricCard';
import type { TestMaturity } from '../../types';

const TEST_TYPES = [
  { key: 'e2e', label: 'E2E Tests' },
  { key: 'unit', label: 'Unit Tests' },
  { key: 'accessibility', label: 'Accessibility Tests' },
  { key: 'security', label: 'Security Tests' },
  { key: 'frontend', label: 'Frontend Tests' },
] as const;

const MATURITY_LEVELS = [
  { value: 0, label: 'None' },
  { value: 1, label: 'Minimal' },
  { value: 3, label: 'Adequate' },
  { value: 5, label: 'Comprehensive' },
];

type TestTypeKey = (typeof TEST_TYPES)[number]['key'];

interface TestMaturityCardProps {
  data: TestMaturity | null | undefined;
  indicatorValue: number | null;
  target: number;
  onSave: (data: Partial<Record<TestTypeKey, number>>) => Promise<unknown>;
  isPending: boolean;
}

function getLevelLabel(value: number | undefined): string {
  if (value === 0) return 'None';
  if (value === 1) return 'Minimal';
  if (value === 3) return 'Adequate';
  if (value === 5) return 'Comprehensive';
  return '—';
}

export default function TestMaturityCard({
  data,
  indicatorValue,
  target,
  onSave,
  isPending,
}: TestMaturityCardProps): JSX.Element {
  const targetNormalized = target / 100;

  return (
    <EditableMetricCard<Partial<Record<TestTypeKey, number>>>
      title="Test Maturity"
      description="Automated testing coverage assessment"
      tooltipContent={<p className="font-mono text-xs">weighted avg of 5 test types</p>}
      indicatorValue={indicatorValue}
      target={target}
      data={data as Partial<Record<TestTypeKey, number>> | null | undefined}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={{}}
      editButtonLabel={data ? 'Edit Assessment' : 'Add Assessment'}
      renderEditForm={(form, setForm) => (
        <>
          {TEST_TYPES.map(({ key, label }) => (
            <div key={key}>
              <label className="text-sm font-medium text-muted-foreground">{label}</label>
              <div className="flex gap-2 mt-2">
                {MATURITY_LEVELS.map((option) => (
                  <Button
                    key={option.value}
                    size="sm"
                    variant={form[key] === option.value ? 'default' : 'outline'}
                    onClick={() => setForm((prev) => ({ ...prev, [key]: option.value }))}
                    className="flex-1"
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
      renderDisplay={(displayData) => (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">Weighted score</span>
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
              {TEST_TYPES.map(({ key, label }) => {
                const value = displayData[key];
                return (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{label.replace(' Tests', '')}</span>
                    <span
                      className={cn(
                        value === 5
                          ? 'text-score-green'
                          : value === 3
                          ? 'text-score-yellow'
                          : value === 1
                          ? 'text-orange-600'
                          : value === 0
                          ? 'text-score-red'
                          : ''
                      )}
                    >
                      {getLevelLabel(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    />
  );
}
