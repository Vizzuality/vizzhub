import { getScoreColor } from '@/components/ui/timeline-chart';
import { formatPeriod, formatShortPeriod, periodKey } from '@/utils/dateUtils';
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

export { formatPeriod as formatPeriodLabel, formatShortPeriod, periodKey };

// Re-export shared getScoreColor as getTimelineScoreColor for backwards compatibility
export const getTimelineScoreColor = getScoreColor;
