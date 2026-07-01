import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import type { MarginSplit } from '../types/portfolio';

export function MarginSplitChart({ data }: { readonly data: MarginSplit }): JSX.Element {
  const rows = [
    { label: 'Gain', value: data.gain, fill: 'var(--score-green)' },
    { label: 'Loss', value: data.loss, fill: 'var(--score-red)' },
    { label: 'No data', value: data.no_data, fill: 'var(--muted-foreground)' },
  ];
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Gain / Loss (margin = 100 − burn)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis allowDecimals={false} fontSize={12} />
            <Tooltip cursor={false} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.label} fill={r.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
