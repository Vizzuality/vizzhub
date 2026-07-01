import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import type { TermBreakdown } from '../types/portfolio';

export function TermBreakdownChart({ data }: { readonly data: TermBreakdown }): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{data.taxonomy_name}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.terms.length === 0 ? (
          <p className="text-muted-foreground text-sm py-8 text-center">
            No tags assigned yet (populated in F2)
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.terms} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} fontSize={12} />
              <YAxis type="category" dataKey="term_name" width={120} fontSize={11} />
              <Tooltip cursor={false} />
              <Bar dataKey="count" fill="var(--chart-3)" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
