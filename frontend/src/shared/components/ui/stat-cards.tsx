import { Card, CardContent } from '@/shared/components/ui/card';

interface StatCardsProps {
  readonly items: readonly { label: string; value: number }[];
  readonly columns?: number;
}

export function StatCards({ items, columns = 4 }: StatCardsProps): JSX.Element {
  const gridColsMap: Record<number, string> = {
    6: 'grid grid-cols-2 md:grid-cols-6 gap-3',
    5: 'grid grid-cols-2 md:grid-cols-5 gap-3',
  };
  const gridClass = gridColsMap[columns] ?? 'grid grid-cols-2 md:grid-cols-4 gap-3';

  return (
    <div className={gridClass}>
      {items.map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="pt-4 pb-4 text-center">
            <p className="text-2xl font-semibold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
