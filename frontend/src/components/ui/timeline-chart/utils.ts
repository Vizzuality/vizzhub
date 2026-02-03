/**
 * Shared utilities for timeline charts.
 */

import { TIMELINE_CHART_COLORS } from './constants';

/**
 * Get the color for a score value based on thresholds.
 * - 80+ = green
 * - 60-79 = yellow
 * - < 60 = red
 * - null = muted
 */
export function getScoreColor(score: number | null): string {
  if (score === null) return TIMELINE_CHART_COLORS.muted;
  if (score >= 80) return TIMELINE_CHART_COLORS.green;
  if (score >= 60) return TIMELINE_CHART_COLORS.yellow;
  return TIMELINE_CHART_COLORS.red;
}

/**
 * Calculate the tick interval for the X-axis based on the number of periods.
 * - > 24 periods = show every 6th tick
 * - > 12 periods = show every 3rd tick
 * - <= 12 periods = show every tick
 */
export function getTickInterval(periodsCount: number): number {
  if (periodsCount > 24) return 5;
  if (periodsCount > 12) return 2;
  return 0;
}
