export const THEME_COLORS: Record<string, { light: string; dark: string }> = {
  'Climate': { light: '#2563eb', dark: '#60a5fa' },
  'Nature & Biodiversity': { light: '#16a34a', dark: '#4ade80' },
  'Oceans & Water': { light: '#0891b2', dark: '#22d3ee' },
  'Food & Land Systems': { light: '#ca8a04', dark: '#facc15' },
  'Energy & Net Zero': { light: '#ea580c', dark: '#fb923c' },
  'Data & Technology': { light: '#7c3aed', dark: '#a78bfa' },
  'Policy & Finance': { light: '#dc2626', dark: '#f87171' },
  'Social Justice': { light: '#db2777', dark: '#f472b6' },
  'Urban & Cities': { light: '#64748b', dark: '#94a3b8' },
  'Other': { light: '#9ca3af', dark: '#d1d5db' },
};

export function getThemeColor(theme: string, isDark: boolean): string {
  const entry = THEME_COLORS[theme] ?? THEME_COLORS['Other'];
  return isDark ? entry.dark : entry.light;
}

export const ROLE_COLORS: Record<string, string> = {
  'Speaker': '#2563eb',
  'Panelist': '#7c3aed',
  'Moderator': '#0891b2',
  'Organizer': '#16a34a',
  'Exhibitor': '#ca8a04',
  'Attendee': '#64748b',
};

export const ALL_SENTINEL = '__all__';

import type { Attending } from '../types/events';

export const ATTENDING_LABELS: Record<Attending, string> = {
  yes: 'Yes',
  maybe: 'Maybe',
  no: 'No',
};

export const ATTENDING_DOT_COLORS: Record<Attending, string> = {
  yes: 'bg-emerald-500',
  maybe: 'bg-amber-500',
  no: 'bg-gray-400',
};

export function buildYearOptions(): string[] {
  const currentYear = new Date().getFullYear();
  const years: string[] = [];
  for (let y = currentYear; y >= 2024; y--) {
    years.push(String(y));
  }
  return years;
}

export function formatEventDateRange(start: string, end: string | null): string {
  const fmt = (d: string): string =>
    new Date(d).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  const s = fmt(start);
  if (!end || end === start) return s;
  return `${s} — ${fmt(end)}`;
}
