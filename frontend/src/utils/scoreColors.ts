/**
 * Utility functions for score color determination.
 * Uses auxiliary palette CSS vars (bg-aux-*, text-aux-*).
 */

export interface ScoreThresholds {
  green: number;
  yellow: number;
}

/**
 * Get the dot background class for a score value.
 * Use with a neutral-colored number beside the dot.
 */
export function getScoreDotClass(
  value: number | null,
  thresholds: ScoreThresholds
): string {
  if (value === null) return 'bg-aux-dust-grey';
  if (value >= thresholds.green) return 'bg-aux-neon-grass';
  if (value >= thresholds.yellow) return 'bg-aux-yellow';
  return 'bg-aux-red';
}

/**
 * Get the text color class for a score value based on thresholds.
 * @deprecated Use getScoreDotClass + neutral text instead.
 */
export function getScoreColor(
  value: number | null,
  thresholds: ScoreThresholds
): string {
  if (value === null) return 'text-muted-foreground';
  if (value >= thresholds.green) return 'text-aux-neon-grass';
  if (value >= thresholds.yellow) return 'text-aux-yellow';
  return 'text-aux-red';
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
