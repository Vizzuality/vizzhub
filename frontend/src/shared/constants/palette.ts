/**
 * Vizzhub auxiliary palette.
 *
 * Defined as CSS custom properties in index.css (--aux-*),
 * mapped to Tailwind classes via tailwind.config.js (aux-*).
 *
 * Neutral scale (charts, heatmaps, tables):
 *   onix → deepTeal → coolSteel → ashGrey → dustGrey → softLinen
 *
 * Accent colors (KPI indicators, alerts):
 *   neonGrass — positive / actual data
 *   red       — negative / over-budget
 *
 * Tailwind usage:  bg-aux-neon-grass, text-aux-red, border-aux-cool-steel
 * JS usage:        AUXILIARY_PALETTE.neonGrass (hex values for Recharts etc.)
 */
export const AUXILIARY_PALETTE = {
  onix: 'var(--aux-onix)',
  deepTeal: 'var(--aux-deep-teal)',
  coolSteel: 'var(--aux-cool-steel)',
  ashGrey: 'var(--aux-ash-grey)',
  dustGrey: 'var(--aux-dust-grey)',
  softLinen: 'var(--aux-soft-linen)',
  neonGrass: 'var(--aux-neon-grass)',
  red: 'var(--aux-red)',
} as const;
