/**
 * Vizzhub auxiliary palette.
 *
 * Earthy tones ordered dark → light for data visualization.
 * Use darkest for primary data, skip one step between series for contrast.
 *
 * Neutral scale (charts, heatmaps, tables):
 *   onix → deepTeal → coolSteel → ashGrey → dustGrey → softLinen
 *
 * Accent colors (KPI indicators, alerts):
 *   neonGrass — positive / actual data
 *   red       — negative / over-budget
 *
 * Usage:
 *   import { AUXILIARY_PALETTE } from '@/shared/constants/palette';
 *   stroke={AUXILIARY_PALETTE.deepTeal}
 */
export const AUXILIARY_PALETTE = {
  onix: '#0C0C0C',
  deepTeal: '#5f7470',
  coolSteel: '#889696',
  ashGrey: '#b8bdb5',
  dustGrey: '#d2d4c8',
  softLinen: '#e0e2db',
  neonGrass: '#5AFF15',
  red: '#DE1A1A',
} as const;
