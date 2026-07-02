import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatAxisEur } from '../utils/chart';

export interface BarDatum {
  readonly label: string;
  readonly value: number;
}

export function LeaderboardBarChart({
  data,
  isCurrency,
}: {
  readonly data: BarDatum[];
  readonly isCurrency: boolean;
}): JSX.Element {
  if (data.length === 0) return <p className="text-muted-foreground text-sm">No data</p>;
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, data.length * 32)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <XAxis type="number" tickFormatter={isCurrency ? formatAxisEur : undefined} fontSize={11} />
        <YAxis type="category" dataKey="label" width={160} fontSize={11} />
        <Tooltip cursor={false} formatter={(v: number) => (isCurrency ? formatAxisEur(v) : v)} />
        <Bar dataKey="value">
          {data.map((d) => (
            <Cell key={d.label} fill={d.value < 0 ? 'var(--destructive)' : 'var(--score-green)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
