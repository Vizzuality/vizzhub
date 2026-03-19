import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/shared/components/ui/card';
import type { AggregationRow, BudgetLine } from '../types/tracker';

interface TimeByAreaTableProps {
  readonly rows: AggregationRow[];
  readonly budgetLines?: BudgetLine[];
}

interface MergedRow {
  name: string;
  contract: number | null;
  spent: number;
  remaining: number | null;
}

function mergeData(rows: AggregationRow[], budgetLines?: BudgetLine[]): MergedRow[] {
  const budgetMap = new Map<string, number>();
  if (budgetLines) {
    for (const bl of budgetLines) {
      const name = bl.functional_area_name ?? bl.details ?? 'Other';
      budgetMap.set(name, (budgetMap.get(name) ?? 0) + (bl.days ?? 0));
    }
  }

  const spentMap = new Map<string, number>();
  for (const r of rows) {
    spentMap.set(r.name, r.total_days);
  }

  const allNames = new Set([...budgetMap.keys(), ...spentMap.keys()]);
  const merged: MergedRow[] = [];

  for (const name of allNames) {
    const contract = budgetMap.get(name) ?? null;
    const spent = spentMap.get(name) ?? 0;
    const remaining = contract !== null ? contract - spent : null;
    merged.push({ name, contract, spent, remaining });
  }

  merged.sort((a, b) => b.spent - a.spent);
  return merged;
}

export default function TimeByAreaTable({ rows, budgetLines }: TimeByAreaTableProps): JSX.Element {
  const merged = useMemo(() => mergeData(rows, budgetLines), [rows, budgetLines]);

  const totalContract = merged.reduce((s, r) => s + (r.contract ?? 0), 0);
  const totalSpent = merged.reduce((s, r) => s + r.spent, 0);
  const totalRemaining = totalContract > 0 ? totalContract - totalSpent : null;
  const hasContract = merged.some((r) => r.contract !== null);

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Time per Functional Area
        </div>
        {merged.length === 0 ? (
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
                {merged.map((row) => (
                  <tr key={row.name} className="border-b last:border-0">
                    <td className="py-2">{row.name}</td>
                    <td className="py-2 text-right tabular-nums">
                      {row.contract !== null ? row.contract : <span className="text-muted-foreground/50">—</span>}
                    </td>
                    <td className="py-2 text-right tabular-nums">{row.spent.toFixed(1)}</td>
                    <td className={cn(
                      'py-2 text-right tabular-nums',
                      row.remaining !== null && row.remaining < 0 && 'text-aux-red',
                    )}>
                      {row.remaining !== null ? row.remaining.toFixed(1) : <span className="text-muted-foreground/50">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium">
                  <td className="pt-2">Total</td>
                  <td className="pt-2 text-right tabular-nums">
                    {hasContract ? totalContract : <span className="text-muted-foreground/50">—</span>}
                  </td>
                  <td className="pt-2 text-right tabular-nums">{totalSpent.toFixed(1)}</td>
                  <td className={cn(
                    'pt-2 text-right tabular-nums',
                    totalRemaining !== null && totalRemaining < 0 && 'text-aux-red',
                  )}>
                    {totalRemaining !== null ? totalRemaining.toFixed(1) : <span className="text-muted-foreground/50">—</span>}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
