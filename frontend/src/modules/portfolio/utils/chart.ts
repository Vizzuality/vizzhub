// Compact euro label for chart Y-axis ticks (e.g. €2.4M, €450k). Mirrors the accrual
// dashboard's formatAxisEur — full-precision currency overflows the narrow axis gutter.
export function formatAxisEur(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `€${Math.round(value / 1_000)}k`;
  return `€${Math.round(value)}`;
}

export const PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#f97316', '#14b8a6', '#a855f7',
  '#84cc16', '#e11d48', '#0ea5e9', '#d946ef', '#eab308',
];
