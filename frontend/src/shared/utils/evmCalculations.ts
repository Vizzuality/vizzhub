export interface EVMCalculatedValues {
  ev: number;
  spi: number | null;
  cpi: number | null;
  hasData: boolean;
}

export function calculateEVMValues(
  budgetTotal: number,
  costToDate: number,
  percentCompleted: number,
  percentPlanned: number,
): EVMCalculatedValues {
  const ev = budgetTotal * percentCompleted;
  const spi = percentPlanned > 0 ? percentCompleted / percentPlanned : null;
  const cpi = costToDate > 0 ? ev / costToDate : null;
  return { ev, spi, cpi, hasData: budgetTotal > 0 };
}

export function formatCurrency(value: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function getPerformanceColor(value: number): string {
  if (value >= 1) return 'text-score-green';
  if (value >= 0.9) return 'text-score-yellow';
  return 'text-score-red';
}

export function getPerformanceLabel(value: number, metric: 'spi' | 'cpi'): string {
  if (metric === 'spi') {
    if (value > 1) return 'Ahead of schedule';
    if (value === 1) return 'On schedule';
    return 'Behind schedule';
  }
  if (value > 1) return 'Under budget';
  if (value === 1) return 'On budget';
  return 'Over budget';
}
