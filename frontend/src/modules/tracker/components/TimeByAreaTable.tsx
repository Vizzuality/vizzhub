import { Card, CardContent } from '@/shared/components/ui/card';
import type { AggregationRow } from '../types/tracker';

interface TimeByAreaTableProps {
  readonly rows: AggregationRow[];
}

export default function TimeByAreaTable({ rows }: TimeByAreaTableProps): JSX.Element {
  const totalDays = rows.reduce((sum, r) => sum + r.total_days, 0);

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Time per Functional Area
        </div>
        {rows.length === 0 ? (
          <p className="text-muted-foreground text-sm">No data</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Functional Area</th>
                  <th className="pb-2 font-medium text-right">Days in Contract</th>
                  <th className="pb-2 font-medium text-right">Spent</th>
                  <th className="pb-2 font-medium text-right">Remaining</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.name} className="border-b last:border-0">
                    <td className="py-2">{row.name}</td>
                    <td className="py-2 text-right text-muted-foreground/50">—</td>
                    <td className="py-2 text-right">{row.total_days.toFixed(2)}</td>
                    <td className="py-2 text-right text-muted-foreground/50">—</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium">
                  <td className="pt-2">Total</td>
                  <td className="pt-2 text-right text-muted-foreground/50">—</td>
                  <td className="pt-2 text-right">{totalDays.toFixed(2)}</td>
                  <td className="pt-2 text-right text-muted-foreground/50">—</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
