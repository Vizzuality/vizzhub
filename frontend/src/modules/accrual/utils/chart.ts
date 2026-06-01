/** Shared chart constants and formatters for the accrual dashboard. */

export const RECOGNIZED_COLOR = 'var(--score-green)';
export const FORECAST_COLOR = 'var(--muted-foreground)';
/** YoY reference line (prior year) — a blue distinct from green and the muted plan. */
export const PRIOR_YEAR_COLOR = 'var(--chart-2)';

/**
 * Compact euro label for chart Y-axis ticks (e.g. €2.4M, €450k). Full-precision
 * `formatCurrency` overflows the narrow axis gutter and clips the leading digits.
 */
export function formatAxisEur(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `€${Math.round(value / 1_000)}k`;
  return `€${Math.round(value)}`;
}
