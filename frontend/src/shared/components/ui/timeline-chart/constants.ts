/**
 * Shared constants for timeline charts.
 */

export const TIMELINE_CHART_COLORS = {
  primary: 'var(--primary)',
  green: 'var(--score-green)',
  yellow: 'var(--score-yellow)',
  red: 'var(--score-red)',
  muted: 'var(--muted-foreground)',
} as const;

export type TimelineChartColor = typeof TIMELINE_CHART_COLORS;
