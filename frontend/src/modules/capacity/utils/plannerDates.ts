// Planner date helpers.
//
// All arithmetic runs in UTC so the returned YYYY-MM-DD string never drifts
// across timezones. Mixing local-time Date with toISOString() subtracts the
// user's TZ offset and can emit the previous day (e.g. Madrid UTC+1 turns a
// Monday input into the preceding Sunday), which then makes the backend
// weeks list include a Monday outside the data-query range and the first
// visible column renders blank.

function parseDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function snapToMonday(d: Date): Date {
  const day = d.getUTCDay();
  const diff = d.getUTCDate() - day + (day === 0 ? -6 : 1);
  const result = new Date(d);
  result.setUTCDate(diff);
  return result;
}

function currentMondayUTC(): Date {
  const now = new Date();
  const today = new Date(
    Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()),
  );
  return snapToMonday(today);
}

export function addMonths(dateStr: string, months: number): string {
  const d = parseDate(dateStr);
  d.setUTCMonth(d.getUTCMonth() + months);
  return formatDate(snapToMonday(d));
}

export function defaultStart(): string {
  // Load 6 past weeks up-front so users see recent planning context
  const monday = currentMondayUTC();
  monday.setUTCDate(monday.getUTCDate() - 6 * 7);
  return formatDate(monday);
}

export function endFromStart(start: string): string {
  return addMonths(start, 6);
}

export function currentMondayString(): string {
  return formatDate(currentMondayUTC());
}

export function snapToMondayString(dateStr: string): string {
  const d = parseDate(dateStr);
  if (d.getUTCDay() === 1) return dateStr;
  return formatDate(snapToMonday(d));
}
