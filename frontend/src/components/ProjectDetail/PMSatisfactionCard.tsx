import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import EditableMetricCard from './EditableMetricCard';
import { IndicatorScoreDisplay, KPIDisplay } from './IndicatorDisplay';
import type { PMSatisfaction } from '../../types';

type ComplaintValue = 'yes' | 'no' | '-';

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
}: PMSatisfactionCardProps): JSX.Element {
  return (
    <EditableMetricCard<PMSatisfactionFormData>
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
            <div className="flex gap-2 mt-2">
              {(['no', 'yes', '-'] as const).map((value) => (
                <Button
                  key={value}
                  size="sm"
                  variant={form.delivery_complaints === value ? 'default' : 'outline'}
                  onClick={() => setForm((prev) => ({ ...prev, delivery_complaints: value }))}
                >
                  {value === '-' ? 'N/A' : value === 'no' ? 'No' : 'Yes'}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Has the client expressed unresolved dissatisfaction with design/implementation?
            </label>
            <div className="flex gap-2 mt-2">
              {(['no', 'yes', '-'] as const).map((value) => (
                <Button
                  key={value}
                  size="sm"
                  variant={form.design_complaints === value ? 'default' : 'outline'}
                  onClick={() => setForm((prev) => ({ ...prev, design_complaints: value }))}
                >
                  {value === '-' ? 'N/A' : value === 'no' ? 'No' : 'Yes'}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Overall estimation of client satisfaction (1-5)
            </label>
            <div className="flex gap-2 mt-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <Button
                  key={value}
                  size="sm"
                  variant={form.overall_estimation === value ? 'default' : 'outline'}
                  onClick={() => setForm((prev) => ({ ...prev, overall_estimation: value }))}
                >
                  {value}
                </Button>
              ))}
            </div>
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
