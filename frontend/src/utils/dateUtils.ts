import { MONTHS_SHORT } from '@/shared/constants/dates';

/**
 * Represents a year-month period.
 */
export interface Period {
  year: number;
  month: number;
}

/**
 * Short month names for display.
 * @deprecated Use MONTHS_SHORT from constants/dates instead
 */
export const MONTH_NAMES = MONTHS_SHORT;

/**
 * Format a period as "Mon YYYY" (e.g., "Jan 2024").
 */
export function formatPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

/**
 * Format a period as "Mon 'YY" (e.g., "Jan '24").
 */
export function formatShortPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} '${String(year).slice(2)}`;
}

/**
 * Generate an array of periods from a start date to an end date (or current month).
 * @param startDate - ISO date string for range start
 * @param endDate - Optional ISO date string for range end (defaults to current month)
 */
export function generateMonthRange(startDate: string, endDate?: string | null): Period[] {
  const start = new Date(startDate);
  const end = endDate ? new Date(endDate) : new Date();
  const periods: Period[] = [];

  let year = start.getFullYear();
  let month = start.getMonth() + 1;

  while (
    year < end.getFullYear() ||
    (year === end.getFullYear() && month <= end.getMonth() + 1)
  ) {
    periods.push({ year, month });
    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return periods;
}

/**
 * Create a unique key for a period.
 */
export function periodKey(year: number, month: number): string {
  return `${year}-${month}`;
}

/**
 * Generate an array of years from past to current year.
 * @param pastYears - Number of past years to include (default: 3)
 * @returns Array of years in descending order (current year first)
 */
export function getYearOptions(pastYears: number = 3): number[] {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: pastYears + 1 }, (_, i) => currentYear - i);
}

/**
 * Calculate the number of months from a start date to now.
 * Used for determining how many historical snapshots to fetch.
 * @param startDate - ISO date string for project start
 * @param minMonths - Minimum months to return (default: 12)
 * @param maxMonths - Maximum months to return (default: 36)
 * @returns Number of months between start and now, clamped to min/max
 */
export function getMonthsSinceStart(
  startDate: string | null | undefined,
  minMonths: number = 12,
  maxMonths: number = 36,
): number {
  if (!startDate) return minMonths;

  const start = new Date(startDate);
  const now = new Date();

  const months =
    (now.getFullYear() - start.getFullYear()) * 12 +
    (now.getMonth() - start.getMonth()) +
    1;

  return Math.max(minMonths, Math.min(maxMonths, months));
}

/**
 * Format a date string as a relative time (e.g., "5m ago", "2h ago", "3d ago").
 * Falls back to locale date string for dates older than 7 days.
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
