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

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Text for a value of unknown type: objects as JSON, never "[object Object]". */
export function toDisplayString(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return value.toString();
  }
  return JSON.stringify(value) ?? '';
}
