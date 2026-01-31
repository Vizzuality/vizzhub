/**
 * Generate an array of years centered around the current year.
 * @param range - Total number of years to include (default: 5)
 * @returns Array of years
 */
export function getYearOptions(range: number = 5): number[] {
  const currentYear = new Date().getFullYear();
  const halfRange = Math.floor(range / 2);
  return Array.from({ length: range }, (_, i) => currentYear - halfRange + i);
}
