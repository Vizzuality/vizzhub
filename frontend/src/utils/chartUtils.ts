import type { Indicators, MetricsWithScores, HistoricalDataPoint } from '../types';
import { formatPeriod } from './formatters';

export const CHART_COLORS = {
  green: 'var(--score-green)',
  red: 'var(--score-red)',
  primary: 'var(--primary)',
} as const;

export const CHART_TOOLTIP_STYLE = {
  backgroundColor: 'var(--popover)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  fontSize: '12px',
} as const;

export function getHistoricalData(
  snapshots: MetricsWithScores[] | undefined,
  indicatorKey: keyof Indicators,
  multiplier = 1,
): HistoricalDataPoint[] {
  if (!snapshots || snapshots.length === 0) return [];
  return snapshots
    .slice()
    .reverse()
    .map((s) => ({
      period: formatPeriod(s.period_year, s.period_month),
      value: s.indicators[indicatorKey] !== null && s.indicators[indicatorKey] !== undefined
        ? (s.indicators[indicatorKey] as number) * multiplier
        : null,
    }));
}
