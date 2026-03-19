import { useMemo } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { cn } from '@/lib/utils';
import { textColorForBg } from '@/shared/utils/colorContrast';
import type { AggregationRow } from '../types/tracker';

interface DaysByPeopleChartProps {
  readonly rows: AggregationRow[];
}

function shortMonth(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

interface HeatmapData {
  people: { name: string; total: number }[];
  months: string[];
  grid: Map<string, number>;
  monthTotals: Map<string, number>;
  maxValue: number;
}

function buildHeatmap(rows: AggregationRow[]): HeatmapData {
  const monthSet = new Set<string>();
  const grid = new Map<string, number>();
  const monthTotals = new Map<string, number>();
  let maxValue = 0;

  for (const row of rows) {
    for (const p of row.periods) {
      monthSet.add(p.date);
      const key = `${row.name}|${p.date}`;
      const val = (grid.get(key) ?? 0) + p.days;
      grid.set(key, val);
      monthTotals.set(p.date, (monthTotals.get(p.date) ?? 0) + p.days);
      if (val > maxValue) maxValue = val;
    }
  }

  const months = [...monthSet].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime(),
  );

  const people = rows
    .map((r) => ({ name: r.name, total: r.total_days }))
    .sort((a, b) => b.total - a.total);

  return { people, months, grid, monthTotals, maxValue };
}

const HEAT_STEPS = [
  { threshold: 0.7, bg: '#5f7470' },
  { threshold: 0.4, bg: '#889696' },
  { threshold: 0.2, bg: '#b8bdb5' },
  { threshold: 0,   bg: '#e0e2db' },
] as const;

function cellStyle(value: number, max: number): { bg: string; text: string } | null {
  if (value === 0 || max === 0) return null;
  const intensity = value / max;
  const step = HEAT_STEPS.find((s) => intensity > s.threshold) ?? HEAT_STEPS[HEAT_STEPS.length - 1];
  return { bg: step.bg, text: textColorForBg(step.bg) };
}

export default function DaysByPeopleChart({ rows }: DaysByPeopleChartProps): JSX.Element | null {
  const { people, months, grid, monthTotals, maxValue } = useMemo(
    () => buildHeatmap(rows),
    [rows],
  );

  if (people.length === 0 || months.length === 0) return null;

  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Days by People
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pb-2 text-left font-medium sticky left-0 bg-card z-10 min-w-[120px]">
                  Name
                </th>
                {months.map((m) => (
                  <th key={m} className="pb-2 text-center font-medium px-1 min-w-[56px]">
                    {shortMonth(m)}
                  </th>
                ))}
                <th className="pb-2 text-right font-medium pl-3 min-w-[52px]">Total</th>
              </tr>
            </thead>
            <tbody>
              {people.map((person) => (
                <tr key={person.name}>
                  <td className="py-0.5 pr-2 text-sm truncate max-w-[160px] sticky left-0 bg-card z-10">
                    {person.name}
                  </td>
                  {months.map((m) => {
                    const val = grid.get(`${person.name}|${m}`) ?? 0;
                    const style = cellStyle(val, maxValue);
                    return (
                      <td key={m} className="py-0.5 px-0.5">
                        <div
                          className={cn(
                            'rounded text-center py-1 px-1 tabular-nums transition-colors',
                            style ? style.text : 'text-muted-foreground/20',
                          )}
                          style={style ? { backgroundColor: style.bg } : undefined}
                          title={`${person.name} — ${shortMonth(m)}: ${val.toFixed(1)} days`}
                        >
                          {val > 0 ? val.toFixed(1) : '·'}
                        </div>
                      </td>
                    );
                  })}
                  <td className="py-0.5 pl-3 text-right text-sm font-medium tabular-nums">
                    {person.total.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t text-muted-foreground">
                <td className="pt-2 text-sm font-medium sticky left-0 bg-card z-10">Total</td>
                {months.map((m) => {
                  const val = monthTotals.get(m) ?? 0;
                  return (
                    <td key={m} className="pt-2 text-center tabular-nums">
                      {val > 0 ? val.toFixed(1) : '·'}
                    </td>
                  );
                })}
                <td className="pt-2 pl-3 text-right text-sm font-medium tabular-nums">
                  {people.reduce((s, p) => s + p.total, 0).toFixed(1)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
