import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { Card, CardContent } from '@/shared/components/ui/card';
import type { AggregationRow } from '../types/tracker';

interface DaysByPeopleChartProps {
  readonly rows: AggregationRow[];
}

const COLORS = [
  '#5f7470', // deep-teal
  '#889696', // cool-steel
  '#b8bdb5', // ash-grey
  '#d2d4c8', // dust-grey-4
  '#D7D9CE', // dust-grey-3
  '#D8DAD0', // dust-grey-2
  '#D9DBD2', // dust-grey
  '#DBDDD4', // soft-linen-3
  '#DDDFD7', // soft-linen-2
  '#e0e2db', // soft-linen
  '#4a5d59', // deep-teal darker
  '#6e8282', // cool-steel darker
  '#a1a89e', // ash-grey darker
  '#c2c5b8', // dust-grey lighter
];

function shortMonth(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

interface ChartPoint {
  label: string;
  [userName: string]: number | string;
}

function buildChartData(rows: AggregationRow[]): { data: ChartPoint[]; people: string[] } {
  const periodMap = new Map<string, Record<string, number>>();
  const people = rows.map((r) => r.name);

  for (const row of rows) {
    for (const p of row.periods) {
      if (!periodMap.has(p.date)) periodMap.set(p.date, {});
      const entry = periodMap.get(p.date)!;
      entry[row.name] = (entry[row.name] ?? 0) + p.days;
    }
  }

  const sorted = [...periodMap.entries()].sort(
    ([a], [b]) => new Date(a).getTime() - new Date(b).getTime(),
  );

  const data: ChartPoint[] = sorted.map(([date, values]) => ({
    label: shortMonth(date),
    ...values,
  }));

  return { data, people };
}

interface PeopleTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ dataKey?: string; value?: number; color?: string }>;
  readonly label?: string;
}

function PeopleTooltip({ active, payload, label }: PeopleTooltipProps): JSX.Element | null {
  if (!active || !payload?.length) return null;
  const visible = payload.filter((p) => p.value && p.value > 0);
  if (visible.length === 0) return null;

  return (
    <div className="bg-popover border rounded px-3 py-2 shadow-lg text-xs space-y-1 max-h-64 overflow-y-auto">
      <div className="font-medium">{label}</div>
      {visible.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground truncate max-w-[120px]">{entry.dataKey}</span>
          <span className="font-medium ml-auto">{entry.value?.toFixed(2)}d</span>
        </div>
      ))}
    </div>
  );
}

export default function DaysByPeopleChart({ rows }: DaysByPeopleChartProps): JSX.Element | null {
  const { data, people } = useMemo(() => buildChartData(rows), [rows]);

  if (data.length === 0) return null;

  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Days by People
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 5, right: 15, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={35}
              label={{ value: 'days', angle: -90, position: 'insideLeft', fontSize: 10, fill: 'var(--muted-foreground)' }}
            />
            <RechartsTooltip content={<PeopleTooltip />} cursor={false} />
            {people.map((name, i) => (
              <Bar
                key={name}
                dataKey={name}
                stackId="people"
                fill={COLORS[i % COLORS.length]}
                radius={i === people.length - 1 ? [2, 2, 0, 0] : [0, 0, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[11px] text-muted-foreground justify-center">
          {people.map((name, i) => (
            <span key={name} className="flex items-center gap-1.5">
              <span
                className="inline-block w-2 h-2 rounded-sm shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              {name}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
