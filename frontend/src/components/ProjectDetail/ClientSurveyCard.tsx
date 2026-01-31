import { Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RatingButtons } from '@/components/ui/RatingButtons';
import EditableMetricCard, { type HistoricalDataPoint } from './EditableMetricCard';
import { IndicatorScoreDisplay, KPIDisplay } from './IndicatorDisplay';
import type { ClientSurvey, ProjectStatus } from '../../types';

const RATING_OPTIONS = [1, 2, 3, 4, 5] as const;

const SURVEY_QUESTIONS = [
  { key: 'understanding', configKey: 'weight_survey_understanding', label: 'Understanding of needs', shortLabel: 'Understanding', defaultWeight: 12 },
  { key: 'proactivity', configKey: 'weight_survey_proactivity', label: 'Proactivity', shortLabel: 'Proactivity', defaultWeight: 12 },
  { key: 'communication', configKey: 'weight_survey_communication', label: 'Communication', shortLabel: 'Communication', defaultWeight: 10 },
  { key: 'delivery_time', configKey: 'weight_survey_time', label: 'Delivery time', shortLabel: 'Delivery', defaultWeight: 14 },
  { key: 'response_time', configKey: 'weight_survey_response', label: 'Response time', shortLabel: 'Response', defaultWeight: 10 },
  { key: 'quality', configKey: 'weight_survey_quality', label: 'Quality of deliverables', shortLabel: 'Quality', defaultWeight: 24 },
  { key: 'expectations', configKey: 'weight_survey_expectations', label: 'Met expectations', shortLabel: 'Expectations', defaultWeight: 12 },
  { key: 'recommend', configKey: 'weight_survey_recommend', label: 'Would recommend', shortLabel: 'Recommend', defaultWeight: 6 },
] as const;

type SurveyKey = (typeof SURVEY_QUESTIONS)[number]['key'];

interface ClientSurveyCardProps {
  data: ClientSurvey | null | undefined;
  indicatorValue: number | null;
  target: number | null;
  projectStatus: ProjectStatus;
  onSave: (data: Partial<Record<SurveyKey, number>>) => Promise<unknown>;
  isPending: boolean;
  getWeight: (name: string) => number | null;
  historicalData?: HistoricalDataPoint[];
}

export default function ClientSurveyCard({
  data,
  indicatorValue,
  target,
  projectStatus,
  onSave,
  isPending,
  getWeight,
  historicalData,
}: ClientSurveyCardProps): JSX.Element {
  const isDisabled = projectStatus === 'in_progress';

  const getQuestionWeight = (configKey: string, defaultWeight: number): string => {
    const weight = getWeight(configKey);
    const pct = weight !== null ? Math.round(weight * 100) : defaultWeight;
    return `${pct}%`;
  };

  return (
    <EditableMetricCard<Partial<Record<SurveyKey, number>>>
      historicalData={historicalData}
      dimension="Satisfaction"
      title="Client Satisfaction Survey"
      description={
        isDisabled
          ? 'Available when project is finished'
          : 'End-of-project client feedback (1-5 scale)'
      }
      tooltipContent={
        <p className="text-sm">
          Weighted average of 8 questions. Quality has highest weight ({getQuestionWeight('weight_survey_quality', 24)}), followed by
          Time ({getQuestionWeight('weight_survey_time', 14)}).
        </p>
      }
      indicatorValue={indicatorValue}
      target={target}
      data={data as Partial<Record<SurveyKey, number>> | null | undefined}
      onSave={onSave}
      isPending={isPending}
      defaultFormState={{}}
      editButtonLabel={data ? 'Edit Survey Results' : 'Add Survey Results'}
      disabled={isDisabled}
      disabledContent={
        <div className="p-4 bg-muted/30 rounded-lg border border-dashed border-muted-foreground/30 text-center">
          <Clock className="h-8 w-8 mx-auto mb-2 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">
            This survey will be available once the project is marked as finished
          </p>
        </div>
      }
      renderEditForm={(form, setForm) => (
        <>
          {SURVEY_QUESTIONS.map(({ key, configKey, label, defaultWeight }) => (
            <div key={key}>
              <div className="flex justify-between items-center mb-1">
                <label className="text-sm font-medium text-muted-foreground">{label}</label>
                <span className="text-xs text-muted-foreground">Weight: {getQuestionWeight(configKey, defaultWeight)}</span>
              </div>
              <RatingButtons
                options={RATING_OPTIONS}
                selected={form[key]}
                onSelect={(value) => setForm((prev) => ({ ...prev, [key]: value }))}
                className="flex gap-1"
                buttonClassName="flex-1"
              />
            </div>
          ))}
        </>
      )}
      renderDisplay={(displayData) => (
        <>
          <IndicatorScoreDisplay
            label="Weighted Score"
            indicatorValue={indicatorValue}
            target={target}
            textSize="md"
          />
          <KPIDisplay target={target} />
          {displayData && (
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/50">
              {SURVEY_QUESTIONS.map(({ key, shortLabel }) => {
                const value = displayData[key];
                return (
                  <div key={key} className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{shortLabel}</span>
                    <span
                      className={cn(
                        value === 5
                          ? 'text-score-green'
                          : value === 4
                          ? 'text-blue-600'
                          : value === 3
                          ? 'text-score-yellow'
                          : value === 2
                          ? 'text-orange-600'
                          : value === 1
                          ? 'text-score-red'
                          : ''
                      )}
                    >
                      {value ?? '—'}
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
