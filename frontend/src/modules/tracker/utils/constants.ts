import { formatCurrency as formatCurrencyBase } from '@/shared/utils/evmCalculations';
import type { ReportingPeriod } from '../types/tracker';

export function formatCurrency(value: number): string {
  return formatCurrencyBase(value, 'euro', 2);
}

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

export function shortMonth(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}


