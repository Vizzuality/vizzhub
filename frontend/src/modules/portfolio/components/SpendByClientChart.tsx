import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { formatAxisEur } from '../utils/chart';
import type { ClientSpend } from '../types/portfolio';

export function SpendByClientChart({ data }: { readonly data: ClientSpend[] }): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Spend per client (top 15, EUR)</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-muted-foreground text-sm py-8 text-center">
            No projects linked to a client yet
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(200, data.length * 28)}>
            <BarChart data={data} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={formatAxisEur} fontSize={12} />
              <YAxis type="category" dataKey="client_name" width={140} fontSize={11} />
              <Tooltip cursor={false} formatter={(v: number) => formatAxisEur(v)} />
              <Bar dataKey="spend_eur" fill="var(--chart-2)" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
