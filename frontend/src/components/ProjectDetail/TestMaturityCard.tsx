import { cn } from '@/lib/utils';
import { RatingButtons } from '@/components/ui/RatingButtons';
import EditableMetricCard, { type HistoricalDataPoint } from './EditableMetricCard';
import { IndicatorScoreDisplay, KPIDisplay } from './IndicatorDisplay';
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

const MATURITY_COLORS: Record<number, string> = {
  5: 'text-score-green',
  3: 'text-score-yellow',
  1: 'text-orange-600',
  0: 'text-score-red',
};

function getMaturityColor(value: number | null | undefined): string {
  return value !== null && value !== undefined ? MATURITY_COLORS[value] ?? '' : '';
}

interface TestMaturityCardProps {
  data: TestMaturity | null | undefined;
  indicatorValue: number | null;
  target: number | null;
  onSave: (data: Partial<Record<TestTypeKey, number>>) => Promise<unknown>;
  isPending: boolean;
  historicalData?: HistoricalDataPoint[];
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
  historicalData,
}: TestMaturityCardProps): JSX.Element {
  return (
    <EditableMetricCard<Partial<Record<TestTypeKey, number>>>
      historicalData={historicalData}
      dimension="Quality"
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
              <RatingButtons
                options={MATURITY_LEVELS}
                selected={form[key]}
                onSelect={(value) => setForm((prev) => ({ ...prev, [key]: value }))}
                className="flex gap-2 mt-2"
                buttonClassName="flex-1"
              />
            </div>
          ))}
        </>
      )}
      renderDisplay={(displayData) => (
        <>
          <IndicatorScoreDisplay
            label="Weighted score"
            indicatorValue={indicatorValue}
            target={target}
          />
          <KPIDisplay target={target} />
          {displayData && (
            <div className="space-y-1 pt-2 border-t border-border/50">
              {TEST_TYPES.map(({ key, label }) => {
                const value = displayData[key];
                return (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{label.replace(' Tests', '')}</span>
                    <span className={cn(getMaturityColor(value))}>
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
