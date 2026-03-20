import { useState } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import {
  useProjectProgress,
  useCreateProgress,
  useUpdateProgress,
  useDeleteProgress,
} from '../hooks/useProgress';
import { formatPeriodDate } from '../utils/constants';
import type { PeriodCostBreakdown, ProgressReport } from '../types/tracker';

interface ProgressCardProps {
  readonly projectId: string;
  readonly periods: PeriodCostBreakdown[];
}

function ProgressBar({ value }: { readonly value: number }): JSX.Element {
  const pct = Math.min(value, 100);
  return (
    <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
      <div
        className="h-full bg-aux-cool-steel rounded-full transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function ProgressCard({ projectId, periods }: ProgressCardProps): JSX.Element {
  const { data: progressList } = useProjectProgress(projectId);
  const createMutation = useCreateProgress(projectId);
  const [adding, setAdding] = useState(false);
  const [newPeriodId, setNewPeriodId] = useState('');
  const [newPct, setNewPct] = useState('');

  const existingPeriodIds = new Set(
    (progressList ?? []).map((p) => p.reporting_period_id),
  );
  const availablePeriods = periods.filter((p) => !existingPeriodIds.has(p.period_id));

  const latestPct = progressList && progressList.length > 0
    ? progressList[progressList.length - 1].percentage
    : null;

  const handleAdd = (): void => {
    const pct = parseFloat(newPct);
    if (!newPeriodId || isNaN(pct) || pct < 0 || pct > 100) return;
    createMutation.mutate(
      { reporting_period_id: newPeriodId, percentage: pct },
      {
        onSuccess: () => {
          setAdding(false);
          setNewPeriodId('');
          setNewPct('');
        },
      },
    );
  };

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Progress
          </div>
          {latestPct !== null && (
            <span className="text-lg font-semibold tabular-nums">
              {latestPct.toFixed(1)}%
            </span>
          )}
        </div>

        {latestPct !== null && <ProgressBar value={latestPct} />}

        {progressList && progressList.length > 0 && (
          <table className="w-full mt-4">
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th className="text-left font-medium pb-1">Period</th>
                <th className="text-right font-medium pb-1">Progress</th>
                <th className="text-right font-medium pb-1">Delta</th>
                <th className="w-16" />
              </tr>
            </thead>
            <tbody>
              {progressList.map((pr) => {
                const deltaPrefix = pr.delta !== null && pr.delta >= 0 ? '+' : '';
                const deltaLabel = pr.delta !== null
                  ? `${deltaPrefix}${pr.delta.toFixed(1)}%`
                  : '\u2014';
                return (
                <tr key={pr.id} className="group/row border-b last:border-0">
                  <td className="py-2 text-sm">
                    {pr.period_date ? formatPeriodDate(pr.period_date) : '—'}
                  </td>
                  <td className="py-2 text-sm text-right tabular-nums">
                    {pr.percentage.toFixed(1)}%
                  </td>
                  <td className="py-2 text-sm text-right tabular-nums text-muted-foreground">
                    {deltaLabel}
                  </td>
                  <td className="py-2 text-right">
                    <ProgressRowActions report={pr} projectId={projectId} />
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {adding ? (
          <div className="flex items-center gap-2 mt-3">
            <select
              className="h-8 rounded border bg-background px-2 text-sm flex-1"
              value={newPeriodId}
              onChange={(e) => setNewPeriodId(e.target.value)}
            >
              <option value="">Select period</option>
              {availablePeriods.map((p) => (
                <option key={p.period_id} value={p.period_id}>
                  {formatPeriodDate(p.date)}
                </option>
              ))}
            </select>
            <Input
              type="number"
              min="0"
              max="100"
              step="1"
              placeholder="%"
              value={newPct}
              onChange={(e) => setNewPct(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              className="w-20 h-8 text-right text-sm"
            />
            <Button size="sm" className="h-8" onClick={handleAdd} disabled={createMutation.isPending}>
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => setAdding(false)}
            >
              Cancel
            </Button>
          </div>
        ) : (
          availablePeriods.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-3 gap-1 text-muted-foreground"
              onClick={() => setAdding(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Add progress
            </Button>
          )
        )}
      </CardContent>
    </Card>
  );
}

function ProgressRowActions({
  report,
  projectId,
}: {
  readonly report: ProgressReport;
  readonly projectId: string;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(report.percentage.toString());
  const updateMutation = useUpdateProgress(projectId);
  const deleteMutation = useDeleteProgress(projectId);

  const handleSave = (): void => {
    const pct = parseFloat(value);
    if (isNaN(pct) || pct < 0 || pct > 100) return;
    updateMutation.mutate(
      { progressId: report.id, data: { percentage: pct } },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1 justify-end">
        <Input
          type="number"
          min="0"
          max="100"
          step="1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          className="w-16 h-7 text-right text-sm"
          autoFocus
        />
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={handleSave}
          disabled={updateMutation.isPending}
        >
          <Check className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 justify-end">
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover/row:opacity-100"
        onClick={() => { setValue(report.percentage.toString()); setEditing(true); }}
      >
        <Pencil className="h-3 w-3" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover/row:opacity-100 text-destructive"
        onClick={() => deleteMutation.mutate(report.id)}
        disabled={deleteMutation.isPending}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  );
}
