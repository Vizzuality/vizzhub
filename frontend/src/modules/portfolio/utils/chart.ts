// Compact euro label for chart Y-axis ticks (e.g. €2.4M, €450k). Mirrors the accrual
// dashboard's formatAxisEur — full-precision currency overflows the narrow axis gutter.
export function formatAxisEur(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `€${Math.round(value / 1_000)}k`;
  return `€${Math.round(value)}`;
}
