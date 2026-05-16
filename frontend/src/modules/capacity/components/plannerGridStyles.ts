export const CURRENT_WEEK_BORDER_LIGHT = '1px solid #2d8a4e';
export const CURRENT_WEEK_BORDER_DARK = '1px solid #5AFF15';
export const CURRENT_WEEK_TINT_LIGHT = 'rgba(45, 138, 78, 0.10)';
export const CURRENT_WEEK_TINT_DARK = 'rgba(90, 255, 21, 0.08)';

const STICKY_LEFT: Record<number, number> = { 0: 0, 1: 50 };

export function stickyLeft(colIdx: number): number | undefined {
  return STICKY_LEFT[colIdx];
}

function ordinalSuffix(day: number): string {
  if (day >= 11 && day <= 13) return 'th';
  switch (day % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
}

export function mondayDayLabel(weekStr: string): string {
  const day = new Date(weekStr + 'T00:00:00').getDate();
  return `${day}${ordinalSuffix(day)}`;
}

export interface WeekStyleConfig {
  currentWeekKey: string;
  currentWeekTint: string;
  currentWeekBorder: string;
  oddMonthBg: string;
  weekMonthInfo: Map<string, { isOddMonth: boolean }>;
}

export function weekCellStyle(
  weekKey: string,
  config: WeekStyleConfig,
): { backgroundColor?: string; borderLeft?: string } {
  const isCurrentWeek = weekKey === config.currentWeekKey;
  const info = config.weekMonthInfo.get(weekKey);
  const monthTint = info?.isOddMonth ? config.oddMonthBg : undefined;
  return {
    backgroundColor: isCurrentWeek ? config.currentWeekTint : monthTint,
    borderLeft: isCurrentWeek ? config.currentWeekBorder : undefined,
  };
}
