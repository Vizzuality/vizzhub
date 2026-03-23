import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useMoods } from '../hooks/useMoods';
import type { NamedFeedbackItem } from '../types/tracker';

const EMOJI_MAP: Record<number, string> = {
  1: '😫',
  2: '😟',
  3: '😐',
  4: '🙂',
  5: '😄',
};

const BAR_COLORS: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-orange-500',
  3: 'bg-yellow-500',
  4: 'bg-green-500',
  5: 'bg-emerald-500',
};

const now = new Date();

function formatMonth(year: number, month: number): string {
  return new Date(year, month - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function navigate(year: number, month: number, direction: 1 | -1): { year: number; month: number } {
  let nextMonth = month + direction;
  let nextYear = year;
  if (nextMonth > 12) {
    nextMonth = 1;
    nextYear += 1;
  } else if (nextMonth < 1) {
    nextMonth = 12;
    nextYear -= 1;
  }
  return { year: nextYear, month: nextMonth };
}

interface MoodBarProps {
  readonly moodKey: number;
  readonly count: number;
  readonly maxCount: number;
}

function MoodBar({ moodKey, count, maxCount }: MoodBarProps): JSX.Element {
  const heightPct = maxCount > 0 ? (count / maxCount) * 100 : 0;

  return (
    <div className="flex flex-col items-center gap-1 flex-1">
      <span className="text-sm font-medium text-foreground">{count}</span>
      <div className="w-full flex items-end" style={{ height: '80px' }}>
        <div
          className={`w-full rounded-t ${BAR_COLORS[moodKey]}`}
          style={{ height: `${heightPct}%`, minHeight: count > 0 ? '4px' : '0' }}
        />
      </div>
      <span className="text-xl">{EMOJI_MAP[moodKey]}</span>
      <span className="text-xs text-muted-foreground">{moodKey}</span>
    </div>
  );
}

interface NamedFeedbackCardProps {
  readonly item: NamedFeedbackItem;
}

function NamedFeedbackCard({ item }: NamedFeedbackCardProps): JSX.Element {
  return (
    <div className="rounded-lg bg-muted/30 p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium text-foreground text-sm">{item.user_name}</span>
        {item.mood !== null && (
          <span className="text-lg">{EMOJI_MAP[item.mood] ?? ''}</span>
        )}
      </div>
      {item.text && (
        <p className="text-sm text-muted-foreground">{item.text}</p>
      )}
    </div>
  );
}

export default function Moods(): JSX.Element {
  const { state, setState } = useUrlState({
    month: { defaultValue: now.getMonth() + 1 },
    year: { defaultValue: now.getFullYear() },
  });

  const { data, isLoading } = useMoods(state.month, state.year);

  const handlePrev = (): void => {
    const next = navigate(state.year, state.month, -1);
    setState(next);
  };

  const handleNext = (): void => {
    const next = navigate(state.year, state.month, 1);
    setState(next);
  };

  const distribution = data?.mood_distribution ?? {};
  const maxCount = Math.max(0, ...Object.values(distribution).map(Number));

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="icon" onClick={handlePrev} aria-label="Previous month">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-xl font-semibold text-foreground min-w-40 text-center">
          {formatMonth(state.year, state.month)}
        </h1>
        <Button variant="outline" size="icon" onClick={handleNext} aria-label="Next month">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Mood Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              {data && (
                <div className="mb-4 flex gap-4 text-sm text-muted-foreground">
                  <span>
                    Responses: <span className="font-medium text-foreground">{data.total_responses}</span>
                    {' / '}
                    {data.total_reports} reports
                  </span>
                  {data.average_mood !== null && (
                    <span>
                      Average: <span className="font-medium text-foreground">{data.average_mood.toFixed(1)}</span>
                      {' '}{EMOJI_MAP[Math.round(data.average_mood)] ?? ''}
                    </span>
                  )}
                </div>
              )}
              <div className="flex gap-3 items-end">
                {[1, 2, 3, 4, 5].map((key) => (
                  <MoodBar
                    key={key}
                    moodKey={key}
                    count={Number(distribution[String(key)] ?? 0)}
                    maxCount={maxCount}
                  />
                ))}
              </div>
              {data && data.total_responses === 0 && (
                <p className="text-sm text-muted-foreground mt-4 text-center">No mood data for this month.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Anonymous Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              {data && data.anonymous_feedback.length > 0 ? (
                <div className="space-y-2">
                  {data.anonymous_feedback.map((text, i) => (
                    <div key={i} className="rounded-lg bg-muted/30 p-3">
                      <p className="text-sm text-foreground">{text}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No anonymous feedback for this month.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Named Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              {data && data.named_feedback.length > 0 ? (
                <div className="space-y-2">
                  {data.named_feedback.map((item, i) => (
                    <NamedFeedbackCard key={i} item={item} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No named feedback for this month.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
