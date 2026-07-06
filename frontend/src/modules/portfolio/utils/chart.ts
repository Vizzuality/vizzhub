// Chart helpers for the portfolio leaderboards. Colors/formatters mirror the
// accrual + tracker dashboards so the leaderboard reads as native to the app.

export type Metric = 'profit_eur' | 'margin_pct' | 'delay_months';

export type SortDir = 'desc' | 'asc';

// Compact euro label for chart axis ticks (e.g. €2.4M, €-450k). Mirrors the
// accrual dashboard's formatAxisEur — full precision overflows the axis gutter.
export function formatAxisEur(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `€${Math.round(value / 1_000)}k`;
  return `€${Math.round(value)}`;
}

// Full euro value for tooltips (e.g. €1,234,567).
export function formatFullEur(value: number): string {
  return `€${Math.round(value).toLocaleString()}`;
}

// Rounded month delay with an explicit + sign for late (e.g. +3mo, -1mo).
export function formatMonths(value: number): string {
  const rounded = Math.round(value);
  const sign = rounded > 0 ? '+' : '';
  return `${sign}${rounded}mo`;
}

export interface MetricConfig {
  readonly key: Metric;
  readonly label: string;
  // Compact form for axis ticks.
  readonly axisFormat: (value: number) => string;
  // Verbose form for tooltips.
  readonly valueFormat: (value: number) => string;
  // True when a value is favourable (green); false is unfavourable (red).
  readonly isGood: (value: number) => boolean;
}

// Per-metric formatting + semantics. Units live here so both the axis and the
// tooltip always carry the magnitude (€ / % / months) — never a bare number.
export const METRIC_CONFIG: Record<Metric, MetricConfig> = {
  profit_eur: {
    key: 'profit_eur',
    label: 'Profit €',
    axisFormat: formatAxisEur,
    valueFormat: formatFullEur,
    isGood: (v) => v >= 0,
  },
  margin_pct: {
    key: 'margin_pct',
    label: 'Margin %',
    axisFormat: (v) => `${Math.round(v)}%`,
    valueFormat: (v) => `${v.toFixed(1)}%`,
    isGood: (v) => v >= 0,
  },
  delay_months: {
    key: 'delay_months',
    label: 'Delay',
    axisFormat: formatMonths,
    valueFormat: formatMonths,
    // On time or early is good; running late is not.
    isGood: (v) => v <= 0,
  },
};

export const METRIC_ORDER: readonly Metric[] = ['profit_eur', 'margin_pct', 'delay_months'];

export const GOOD_COLOR = 'var(--score-green)';
export const BAD_COLOR = 'var(--score-red)';

export function barColor(value: number, metric: Metric): string {
  return METRIC_CONFIG[metric].isGood(value) ? GOOD_COLOR : BAD_COLOR;
}
