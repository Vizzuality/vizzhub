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
 *   yellow    — neutral / warning
 *   amber     — secondary forecast / projection (distinct from yellow + red)
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
  yellow: 'var(--aux-yellow)',
  amber: 'var(--aux-amber)',
  red: 'var(--aux-red)',
} as const;

/**
 * Raw hex values for contexts that cannot use CSS variables
 * (Recharts fills/strokes, inline styles, canvas rendering).
 */
export const PALETTE_HEX = {
  onix: '#0C0C0C',
  deepTeal: '#5f7470',
  coolSteel: '#889696',
  ashGrey: '#b8bdb5',
  dustGrey: '#d2d4c8',
  softLinen: '#e0e2db',
  neonGrass: '#5AFF15',
  yellow: '#FFD23F',
  amber: '#F97316',
  red: '#DE1A1A',
} as const;
