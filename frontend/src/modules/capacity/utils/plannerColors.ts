interface ColorRange {
  min: number;
  max: number;
  light: string;
  dark: string;
}

const RANGES: ColorRange[] = [
  { min: 1, max: 20, light: '#D9EAD3', dark: '#2A3B28' },
  { min: 21, max: 40, light: '#FFE599', dark: '#4A3D1A' },
  { min: 41, max: 60, light: '#F9CB9C', dark: '#4A2E1A' },
  { min: 61, max: 80, light: '#F6B26B', dark: '#4A2A10' },
  { min: 81, max: 100, light: '#E06666', dark: '#4A1A1A' },
  { min: 101, max: 200, light: '#8E7CC3', dark: '#2E2450' },
];

export function getPlannerCellColor(
  percentage: number | undefined,
  isDark: boolean,
): string | undefined {
  if (percentage === undefined) return undefined;
  const range = RANGES.find((r) => percentage >= r.min && percentage <= r.max);
  if (!range) return undefined;
  return isDark ? range.dark : range.light;
}
