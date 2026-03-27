interface ColorRange {
  min: number;
  max: number;
  light: string;
  dark: string;
  lightText?: string;
}

const RANGES: ColorRange[] = [
  { min: 1, max: 20, light: '#D9EAD3', dark: '#3D6B35' },
  { min: 21, max: 40, light: '#FFE599', dark: '#7A6A2A' },
  { min: 41, max: 60, light: '#F9CB9C', dark: '#8A5A2A' },
  { min: 61, max: 80, light: '#F6B26B', dark: '#8A4A15' },
  { min: 81, max: 100, light: '#E06666', dark: '#7A2A2A', lightText: '#fff' },
  { min: 101, max: 200, light: '#8E7CC3', dark: '#5A4A8A', lightText: '#fff' },
];

export interface CellColors {
  bg: string;
  text?: string;
}

export function getPlannerCellColors(
  percentage: number | undefined,
  isDark: boolean,
): CellColors | undefined {
  if (percentage === undefined) return undefined;
  const range = RANGES.find((r) => percentage >= r.min && percentage <= r.max);
  if (!range) return undefined;
  return {
    bg: isDark ? range.dark : range.light,
    text: !isDark ? range.lightText : undefined,
  };
}
