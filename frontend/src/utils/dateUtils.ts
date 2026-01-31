/**
 * Generate an array of years from past to current year.
 * @param pastYears - Number of past years to include (default: 3)
 * @returns Array of years in descending order (current year first)
 */
export function getYearOptions(pastYears: number = 3): number[] {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: pastYears + 1 }, (_, i) => currentYear - i);
}
