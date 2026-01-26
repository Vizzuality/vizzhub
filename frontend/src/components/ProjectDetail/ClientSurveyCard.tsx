import { Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import EditableMetricCard from './EditableMetricCard';
import type { ClientSurvey, ProjectStatus } from '../../types';

const SURVEY_QUESTIONS = [
  { key: 'understanding', label: 'Understanding of needs', weight: '12%', shortLabel: 'Understanding' },
  { key: 'proactivity', label: 'Proactivity', weight: '12%', shortLabel: 'Proactivity' },
  { key: 'communication', label: 'Communication', weight: '10%', shortLabel: 'Communication' },
  { key: 'delivery_time', label: 'Delivery time', weight: '14%', shortLabel: 'Delivery' },
  { key: 'response_time', label: 'Response time', weight: '10%', shortLabel: 'Response' },
  { key: 'quality', label: 'Quality of deliverables', weight: '24%', shortLabel: 'Quality' },
  { key: 'expectations', label: 'Met expectations', weight: '12%', shortLabel: 'Expectations' },
  { key: 'recommend', label: 'Would recommend', weight: '6%', shortLabel: 'Recommend' },
] as const;

type SurveyKey = (typeof SURVEY_QUESTIONS)[number]['key'];

interface ClientSurveyCardProps {
  data: ClientSurvey | null | undefined;
  indicatorValue: number | null;
  target: number;
  projectStatus: ProjectStatus;
  onSave: (data: Partial<Record<SurveyKey, number>>) => Promise<unknown>;
  isPending: boolean;
}

export default function ClientSurveyCard({
  data,
  indicatorValue,
  target,
  projectStatus,
  onSave,
  isPending,
}: ClientSurveyCardProps): JSX.Element {
  const targetNormalized = target / 100;
  const isDisabled = projectStatus === 'in_progress';

  return (
    <EditableMetricCard<Partial<Record<SurveyKey, number>>>
      title="Client Satisfaction Survey"
      description={
        isDisabled
          ? 'Available when project is finished'
          : 'End-of-project client feedback (1-5 scale)'
      }
      tooltipContent={
        <p className="text-sm">
          Weighted average of 8 questions. Quality has highest weight (24%), followed by
          Time (14%).
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
          {SURVEY_QUESTIONS.map(({ key, label, weight }) => (
            <div key={key}>
              <div className="flex justify-between items-center mb-1">
                <label className="text-sm font-medium text-muted-foreground">{label}</label>
                <span className="text-xs text-muted-foreground">Weight: {weight}</span>
              </div>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((value) => (
                  <Button
                    key={value}
                    size="sm"
                    variant={form[key] === value ? 'default' : 'outline'}
                    onClick={() => setForm((prev) => ({ ...prev, [key]: value }))}
                    className="flex-1"
                  >
                    {value}
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
            <span className="text-sm font-medium text-muted-foreground">Weighted Score</span>
            <span
              className={cn(
                'text-2xl font-bold',
                indicatorValue === null
                  ? 'text-muted-foreground'
                  : indicatorValue >= targetNormalized
                  ? 'text-score-green'
                  : indicatorValue >= targetNormalized * 0.9
                  ? 'text-score-yellow'
                  : 'text-score-red'
              )}
            >
              {indicatorValue !== null ? `${Math.round(indicatorValue * 100)}%` : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-border/50">
            <span className="text-xs text-muted-foreground">KPI</span>
            <span className="text-sm text-foreground">≥{target}%</span>
          </div>
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
