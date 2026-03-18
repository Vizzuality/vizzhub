import type { ReportingPeriod } from '../types/tracker';

export function formatPeriodDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
}

export const PERIOD_STATUS_COLORS: Record<ReportingPeriod['status'], string> = {
  unstarted: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  finished: 'bg-blue-100 text-blue-700',
};

export const SELECT_CLASS = 'flex rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring';

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(value);
}

export function burnColor(pct: number): string {
  if (pct > 100) return 'bg-destructive';
  if (pct >= 80) return 'bg-yellow-500';
  return 'bg-primary';
}
