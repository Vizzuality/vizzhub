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
