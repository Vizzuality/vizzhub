import { useMemo } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import type { AggregationRow } from '../types/tracker';

interface DaysTableProps {
  readonly rows: AggregationRow[];
  readonly lastNMonths?: number;
}

function shortMonth(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

interface TableData {
  columns: string[];
  people: {
    name: string;
    area: string | null;
    byMonth: Record<string, number>;
    total: number;
  }[];
}

function buildTableData(rows: AggregationRow[], lastN: number): TableData {
  const allDates = new Set<string>();
  for (const row of rows) {
    for (const p of row.periods) {
      allDates.add(p.date);
    }
  }

  const sortedDates = [...allDates].sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime(),
  );
  const columns = sortedDates.slice(-lastN);

  const people = rows.map((row) => {
    const byMonth: Record<string, number> = {};
    let total = 0;
    for (const p of row.periods) {
      if (columns.includes(p.date)) {
        byMonth[p.date] = (byMonth[p.date] ?? 0) + p.days;
        total += p.days;
      }
    }
    return { name: row.name, area: row.email, byMonth, total };
  });

  people.sort((a, b) => b.total - a.total);

  return { columns, people };
}

export default function DaysTable({ rows, lastNMonths = 5 }: DaysTableProps): JSX.Element | null {
  const { columns, people } = useMemo(
    () => buildTableData(rows, lastNMonths),
    [rows, lastNMonths],
  );

  if (people.length === 0) return null;

  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Days in the Last {columns.length} Months
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-2 font-medium">Name</th>
                {columns.map((date) => (
                  <th key={date} className="pb-2 font-medium text-right">
                    {shortMonth(date)}
                  </th>
                ))}
                <th className="pb-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {people.map((person) => (
                <tr key={person.name} className="border-b last:border-0">
                  <td className="py-1.5">{person.name}</td>
                  {columns.map((date) => {
                    const val = person.byMonth[date];
                    return (
                      <td key={date} className="py-1.5 text-right tabular-nums">
                        {val ? val.toFixed(1) : <span className="text-muted-foreground/30">0</span>}
                      </td>
                    );
                  })}
                  <td className="py-1.5 text-right font-medium tabular-nums">
                    {person.total.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
