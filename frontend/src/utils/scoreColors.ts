/**
 * Utility functions for score color determination.
 */

export interface ScoreThresholds {
  green: number;
  yellow: number;
}

/**
 * Get the text color class for a score value based on thresholds.
 */
export function getScoreColor(
  value: number | null,
  thresholds: ScoreThresholds
): string {
  if (value === null) return 'text-muted-foreground';
  if (value >= thresholds.green) return 'text-score-green';
  if (value >= thresholds.yellow) return 'text-score-yellow';
  return 'text-score-red';
}

/**
 * Get the background color class for a score value based on thresholds.
 */
export function getScoreBgColor(
  value: number | null,
  thresholds: ScoreThresholds
): string {
  if (value === null) return 'bg-muted';
  if (value >= thresholds.green) return 'bg-score-green-bg';
  if (value >= thresholds.yellow) return 'bg-score-yellow-bg';
  return 'bg-score-red-bg';
}
