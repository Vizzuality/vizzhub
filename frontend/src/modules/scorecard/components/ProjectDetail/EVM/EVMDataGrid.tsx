import type { EVMData } from '@/modules/scorecard/types';
import { formatCurrency } from '@/shared/utils/evmCalculations';

interface EVMDataGridProps {
  evmData: EVMData;
  currency?: string;
}

interface DataItem {
  label: string;
  value: string;
}

export default function EVMDataGrid({ evmData, currency }: EVMDataGridProps): JSX.Element {
  const items: DataItem[] = [
    { label: 'Total Budget', value: formatCurrency(evmData.budget_total, currency) },
    { label: 'Actual Cost', value: formatCurrency(evmData.cost_to_date, currency) },
    { label: 'Work Completed', value: `${(evmData.percent_completed * 100).toFixed(0)}%` },
    { label: 'Expected Progress', value: `${(evmData.percent_planned * 100).toFixed(0)}%` },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map((item) => (
        <div key={item.label} className="p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">{item.label}</p>
          <p className="text-2xl font-semibold">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
