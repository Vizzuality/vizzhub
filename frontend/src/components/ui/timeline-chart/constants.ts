/**
 * Shared constants for timeline charts.
 */

export const TIMELINE_CHART_COLORS = {
  primary: '#6366f1',
  green: '#22c55e',
  yellow: '#eab308',
  red: '#ef4444',
  muted: '#71717a',
} as const;

export type TimelineChartColor = typeof TIMELINE_CHART_COLORS;
