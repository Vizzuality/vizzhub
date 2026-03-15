export const DATE_INPUT_MIN = '2015-01-01';
export const DATE_INPUT_MAX = '2099-12-31';

export const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const;

export const MONTHS_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
] as const;

export type MonthName = (typeof MONTHS)[number];
export type MonthNameShort = (typeof MONTHS_SHORT)[number];
