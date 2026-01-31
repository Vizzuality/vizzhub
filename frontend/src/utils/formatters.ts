/**
 * Shared utility functions for formatting values.
 */

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatDate(dateString: string | null): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year.toString().slice(-2)}`;
}

export function isDimensionVisible(visibleDimensions: Set<string> | undefined, dimension: string): boolean {
  return !visibleDimensions || visibleDimensions.has(dimension);
}
