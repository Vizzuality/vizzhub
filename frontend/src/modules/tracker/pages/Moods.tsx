import { useMemo, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useMoods, useDeleteAnonymousFeedback, useDeleteReportMood } from '../hooks/useMoods';
import { useReportingPeriods } from '../hooks/useReportingPeriods';
import { formatPeriodDate, MOOD_EMOJIS, MOOD_BAR_COLORS } from '../utils/constants';
import MoodTrend from '../components/MoodTrend';
import type { NamedFeedbackItem } from '../types/tracker';

const now = new Date();

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
          className={`w-full rounded-t ${MOOD_BAR_COLORS[moodKey]}`}
          style={{ height: `${heightPct}%`, minHeight: count > 0 ? '4px' : '0' }}
        />
      </div>
      <span className="text-xl">{MOOD_EMOJIS[moodKey]}</span>
      <span className="text-xs text-muted-foreground">{moodKey}</span>
    </div>
  );
}

interface NamedFeedbackCardProps {
  readonly item: NamedFeedbackItem;
  readonly onDelete: () => void;
}

function NamedFeedbackCard({ item, onDelete }: NamedFeedbackCardProps): JSX.Element {
  return (
    <div className="rounded-lg bg-muted/30 p-3 flex items-start justify-between gap-2">
      <div className="min-w-0">
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
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 h-7 w-7 text-muted-foreground hover:text-destructive"
        onClick={onDelete}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

export default function Moods(): JSX.Element {
  const { state, setState } = useUrlState({
    month: { defaultValue: now.getMonth() + 1 },
    year: { defaultValue: now.getFullYear() },
    tab: { defaultValue: 'monthly' },
  });

  const { data: periods } = useReportingPeriods();
  const isMonthlyTab = state.tab === 'monthly';
  const { data, isLoading } = useMoods(state.month, state.year, { enabled: isMonthlyTab });
  const deleteAnon = useDeleteAnonymousFeedback(state.month, state.year);
  const deleteMood = useDeleteReportMood(state.month, state.year);

  const [deleteTarget, setDeleteTarget] = useState<
    { type: 'anonymous'; id: string } | { type: 'named'; reportId: string; userName: string } | null
  >(null);

  const sortedPeriods = useMemo(
    () => [...(periods ?? [])].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
    ),
    [periods],
  );

  const selectedValue = `${state.year}-${String(state.month).padStart(2, '0')}`;

  const handlePeriodChange = (value: string): void => {
    const d = new Date(value + '-01');
    setState({ month: d.getMonth() + 1, year: d.getFullYear() });
  };

  const handleConfirmDelete = (): void => {
    if (!deleteTarget) return;
    if (deleteTarget.type === 'anonymous') {
      deleteAnon.mutate(deleteTarget.id);
    } else {
      deleteMood.mutate(deleteTarget.reportId);
    }
    setDeleteTarget(null);
  };

  const distribution = data?.mood_distribution ?? {};
  const maxCount = Math.max(0, ...Object.values(distribution).map(Number));

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-xl font-semibold text-foreground">Team Moods</h1>

      <Tabs value={state.tab} onValueChange={(tab) => setState({ tab })}>
        <TabsList>
          <TabsTrigger value="monthly">Monthly</TabsTrigger>
          <TabsTrigger value="trend">Trend</TabsTrigger>
        </TabsList>

        <TabsContent value="monthly" className="space-y-6 mt-4">
          <div className="flex items-center gap-3">
            <select
              value={selectedValue}
              onChange={(e) => handlePeriodChange(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              {sortedPeriods.map((p) => {
                const d = new Date(p.date);
                const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
                return (
                  <option key={p.id} value={val}>
                    {formatPeriodDate(p.date)}
                  </option>
                );
              })}
            </select>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : (
            <>
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
                          {' '}{MOOD_EMOJIS[Math.round(data.average_mood)] ?? ''}
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
                  {data?.total_responses === 0 && (
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
                      {data.anonymous_feedback.map((item) => (
                        <div key={item.id} className="rounded-lg bg-muted/30 p-3 flex items-start justify-between gap-2">
                          <p className="text-sm text-foreground min-w-0">{item.text}</p>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="shrink-0 h-7 w-7 text-muted-foreground hover:text-destructive"
                            onClick={() => setDeleteTarget({ type: 'anonymous', id: item.id })}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
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
                      {data.named_feedback.map((item) => (
                        <NamedFeedbackCard
                          key={item.report_id}
                          item={item}
                          onDelete={() => setDeleteTarget({ type: 'named', reportId: item.report_id, userName: item.user_name })}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No named feedback for this month.</p>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="trend" className="mt-4">
          <MoodTrend />
        </TabsContent>
      </Tabs>

      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete feedback</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.type === 'anonymous'
                ? 'This will permanently delete this anonymous feedback entry.'
                : `This will clear mood and feedback for ${deleteTarget?.userName ?? ''}.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
