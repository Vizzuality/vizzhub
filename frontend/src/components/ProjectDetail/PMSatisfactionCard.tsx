import { cn } from '@/lib/utils';
import { RatingButtons } from '@/components/ui/RatingButtons';
import EditableMetricCard, { type HistoricalDataPoint } from './EditableMetricCard';
import { IndicatorScoreDisplay, KPIDisplay } from './IndicatorDisplay';
import type { PMSatisfaction } from '../../types';

type ComplaintValue = 'yes' | 'no' | '-';

const COMPLAINT_OPTIONS = [
  { value: 'no' as const, label: 'No' },
  { value: 'yes' as const, label: 'Yes' },
  { value: '-' as const, label: 'N/A' },
];

const RATING_OPTIONS = [1, 2, 3, 4, 5] as const;

interface PMSatisfactionFormData {
  delivery_complaints: ComplaintValue;
  design_complaints: ComplaintValue;
  overall_estimation?: number;
}

interface PMSatisfactionCardProps {
  data: PMSatisfaction | null | undefined;
  indicatorValue: number | null;
  target: number | null;
  onSave: (data: PMSatisfactionFormData) => Promise<unknown>;
  isPending: boolean;
  historicalData?: HistoricalDataPoint[];
}

const DEFAULT_FORM: PMSatisfactionFormData = {
  delivery_complaints: '-',
  design_complaints: '-',
  overall_estimation: undefined,
};

export default function PMSatisfactionCard({
  data,
  indicatorValue,
  target,
  onSave,
  isPending,
  historicalData,
}: PMSatisfactionCardProps): JSX.Element {
  return (
    <EditableMetricCard<PMSatisfactionFormData>
      historicalData={historicalData}
      title="Client Satisfaction (PM Est.)"
      description="PM estimation of client satisfaction"
      tooltipContent={<p className="font-mono text-xs">0.3×delivery + 0.3×design + 0.4×overall</p>}
      indicatorValue={indicatorValue}
      target={target}
      data={data as PMSatisfactionFormData | null | undefined}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={DEFAULT_FORM}
      editButtonLabel={data ? 'Edit Estimation' : 'Add Estimation'}
      renderEditForm={(form, setForm) => (
        <>
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Has the client complained about delays or delivery quality?
            </label>
            <RatingButtons
              options={COMPLAINT_OPTIONS}
              selected={form.delivery_complaints}
              onSelect={(value) => setForm((prev) => ({ ...prev, delivery_complaints: value }))}
              className="flex gap-2 mt-2"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Has the client expressed unresolved dissatisfaction with design/implementation?
            </label>
            <RatingButtons
              options={COMPLAINT_OPTIONS}
              selected={form.design_complaints}
              onSelect={(value) => setForm((prev) => ({ ...prev, design_complaints: value }))}
              className="flex gap-2 mt-2"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Overall estimation of client satisfaction (1-5)
            </label>
            <RatingButtons
              options={RATING_OPTIONS}
              selected={form.overall_estimation}
              onSelect={(value) => setForm((prev) => ({ ...prev, overall_estimation: value }))}
              className="flex gap-2 mt-2"
            />
          </div>
        </>
      )}
      renderDisplay={(displayData) => (
        <>
          <IndicatorScoreDisplay
            label="Normalized score"
            indicatorValue={indicatorValue}
            target={target}
          />
          <KPIDisplay target={target} />
          {displayData && (
            <div className="space-y-1 pt-2 border-t border-border/50">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Delivery complaints</span>
                <span
                  className={cn(
                    displayData.delivery_complaints === 'no'
                      ? 'text-score-green'
                      : displayData.delivery_complaints === 'yes'
                      ? 'text-score-red'
                      : ''
                  )}
                >
                  {displayData.delivery_complaints === '-' ? 'N/A' : displayData.delivery_complaints}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Design complaints</span>
                <span
                  className={cn(
                    displayData.design_complaints === 'no'
                      ? 'text-score-green'
                      : displayData.design_complaints === 'yes'
                      ? 'text-score-red'
                      : ''
                  )}
                >
                  {displayData.design_complaints === '-' ? 'N/A' : displayData.design_complaints}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Overall (1-5)</span>
                <span>{displayData.overall_estimation ?? '—'}</span>
              </div>
            </div>
          )}
        </>
      )}
    />
  );
}
