/**
 * Shared utility functions for formatting values.
 */

import { MONTHS_SHORT } from '@/shared/constants/dates';

export function formatDate(dateString: string | null): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatPeriod(year: number, month: number): string {
  return `${MONTHS_SHORT[month - 1]} ${year.toString().slice(-2)}`;
}

export function getFullName(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  fallback = '',
): string {
  return [firstName, lastName].filter(Boolean).join(' ') || fallback;
}

export function getInitials(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
): string {
  return [firstName, lastName]
    .filter(Boolean)
    .map((n) => n![0])
    .join('')
    .toUpperCase() || '?';
}
