import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useMoodsTrend } from '../hooks/useMoods';
import { MOOD_EMOJIS, MOOD_HEX_COLORS } from '../utils/constants';
import type { TrendMonth } from '../types/tracker';

function getMoodColor(avg: number): string {
  const rounded = Math.round(avg);
  return MOOD_HEX_COLORS[rounded] ?? '#6b7280';
}

interface TrendBarProps {
  readonly month: TrendMonth;
}

function TrendBar({ month }: TrendBarProps): JSX.Element {
  const avg = month.average_mood;
  const heightPct = avg === null ? 0 : (avg / 5) * 100;

  return (
    <div className="flex flex-col items-center gap-1 flex-1 min-w-0">
      {avg === null ? (
        <span className="text-xs text-muted-foreground">-</span>
      ) : (
        <span className="text-xs font-medium text-foreground">{avg.toFixed(1)}</span>
      )}
      <div className="w-full flex items-end" style={{ height: '100px' }}>
        {avg === null ? (
          <div className="w-full rounded-t bg-muted" style={{ height: '2px' }} />
        ) : (
          <div
            className="w-full rounded-t"
            style={{
              height: `${heightPct}%`,
              minHeight: '4px',
              backgroundColor: getMoodColor(avg),
            }}
          />
        )}
      </div>
      <span className="text-[10px] text-muted-foreground leading-tight text-center">
        {month.label.split(' ')[0]}
      </span>
    </div>
  );
}

function FeedbackByMonth({ months }: { readonly months: TrendMonth[] }): JSX.Element {
  const withFeedback = months.filter(
    (m) => m.anonymous_feedback.length > 0 || m.named_feedback.length > 0,
  );

  if (withFeedback.length === 0) {
    return <p className="text-sm text-muted-foreground">No feedback in the last 12 months.</p>;
  }

  return (
    <div className="space-y-6">
      {withFeedback.map((m) => (
        <div key={`${m.year}-${m.month}`}>
          <h4 className="text-sm font-medium text-foreground mb-2">{m.label}</h4>
          <div className="space-y-2">
            {m.anonymous_feedback.map((item) => (
              <div key={item.id} className="rounded-lg bg-muted/30 p-3">
                <p className="text-sm text-foreground">{item.text}</p>
                <span className="text-xs text-muted-foreground">Anonymous</span>
              </div>
            ))}
            {m.named_feedback.map((item) => (
              <div key={item.report_id} className="rounded-lg bg-muted/30 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-foreground text-sm">{item.user_name}</span>
                  {item.mood !== null && (
                    <span className="text-lg">{MOOD_EMOJIS[item.mood] ?? ''}</span>
                  )}
                </div>
                {item.text && (
                  <p className="text-sm text-muted-foreground">{item.text}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MoodTrend(): JSX.Element {
  const { data, isLoading } = useMoodsTrend();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  const months = data?.months ?? [];
  const withData = months.filter((m) => m.average_mood !== null);
  const overallAvg = withData.length > 0
    ? withData.reduce((sum, m) => sum + m.average_mood!, 0) / withData.length
    : null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Mood Trend — Last 12 Months</CardTitle>
        </CardHeader>
        <CardContent>
          {overallAvg !== null && (
            <div className="mb-4 text-sm text-muted-foreground">
              Overall average: <span className="font-medium text-foreground">{overallAvg.toFixed(1)}</span>
              {' '}{MOOD_EMOJIS[Math.round(overallAvg)] ?? ''}
              {' · '}{withData.length} months with data
            </div>
          )}
          <div className="flex gap-1 items-end">
            {months.map((m) => (
              <TrendBar key={`${m.year}-${m.month}`} month={m} />
            ))}
          </div>
          {withData.length === 0 && (
            <p className="text-sm text-muted-foreground mt-4 text-center">No mood data in the last 12 months.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Feedback History</CardTitle>
        </CardHeader>
        <CardContent>
          <FeedbackByMonth months={months} />
        </CardContent>
      </Card>
    </div>
  );
}
