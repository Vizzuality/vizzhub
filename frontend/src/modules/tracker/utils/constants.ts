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

export { shortMonth } from '@/shared/constants/dates';

export const MOOD_EMOJIS: Record<number, string> = {
  1: '\u{1F62B}',
  2: '\u{1F61F}',
  3: '\u{1F610}',
  4: '\u{1F642}',
  5: '\u{1F604}',
};

export const MOOD_ITEMS = [
  { value: 1, emoji: '\u{1F62B}', label: 'Very bad' },
  { value: 2, emoji: '\u{1F61F}', label: 'Bad' },
  { value: 3, emoji: '\u{1F610}', label: 'Neutral' },
  { value: 4, emoji: '\u{1F642}', label: 'Good' },
  { value: 5, emoji: '\u{1F604}', label: 'Very good' },
] as const;

export const MOOD_BAR_COLORS: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-orange-500',
  3: 'bg-yellow-500',
  4: 'bg-green-500',
  5: 'bg-emerald-500',
};

export const MOOD_HEX_COLORS: Record<number, string> = {
  1: '#ef4444',
  2: '#f97316',
  3: '#eab308',
  4: '#22c55e',
  5: '#10b981',
};
