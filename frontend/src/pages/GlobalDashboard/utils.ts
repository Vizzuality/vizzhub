import { getScoreColor } from '@/components/ui/timeline-chart';
import { MONTHS_SHORT } from '../../constants/dates';
import { TIMELINE_MONTHS } from './constants';
import type { Period } from './types';

export function generateGlobalMonthRange(monthsBack: number = TIMELINE_MONTHS): Period[] {
  const periods: Period[] = [];
  const now = new Date();
  let year = now.getFullYear();
  let month = now.getMonth() + 1;

  for (let i = 0; i < monthsBack; i++) {
    periods.unshift({ year, month });
    month--;
    if (month < 1) {
      month = 12;
      year--;
    }
  }

  return periods;
}

export function formatPeriodLabel(year: number, month: number): string {
  return `${MONTHS_SHORT[month - 1]} ${year}`;
}

export function formatShortPeriod(year: number, month: number): string {
  return `${MONTHS_SHORT[month - 1].slice(0, 3)} '${year.toString().slice(-2)}`;
}

export function periodKey(year: number, month: number): string {
  return `${year}-${month}`;
}

// Re-export shared getScoreColor as getTimelineScoreColor for backwards compatibility
export const getTimelineScoreColor = getScoreColor;
