/** MTTR (business hours): average hours between created and resolved,
 * counting only business hours (Mon–Fri, 09:00–17:00 local script TZ).
 * Scope: issuetype IN (Incident, Bug) AND priority IN (Highest, High, "Fix Now") AND Done.
 * Writes into the row labeled "MTTR_hours" in Data_Forms (col B).
 */

// ---- Config ----
const MTTR_BIZ_CFG = {
  ISSUE_TYPES: ['Incident', 'Bug'],
  PRIORITIES:  ['Highest', 'High', 'Fix now'],
  EXTRA_JQL:   '', // e.g., 'AND labels = Sev1'
  FIELDS:      ['created','resolutiondate'],
  PAGE_SIZE:   100,
  WORK_START_HOUR: 9,   // 09:00
  WORK_END_HOUR:   17,  // 17:00 (8h window)
};

// ---- Public command ----
function cmd_updateMttr() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Data_Forms');
  if (!sheet) { SpreadsheetApp.getUi().alert("Missing sheet 'Data_Forms'."); return; }

  const key = String(sheet.getRange('B2').getValue() || '').trim();
  if (!key) { SpreadsheetApp.getUi().alert('Missing Project Key in Data_Forms!B2.'); return; }

  const proj = getProjectByKey_(key);
  if (!proj) { SpreadsheetApp.getUi().alert(`Project key not found or no access: "${key}"`); return; }

  // Build JQL with grouped OR: (Incident) OR (Bug AND priority in ...)
  const typesIncident = '"Incident"';
  const typeBug = '"Bug"';
  const prios = MTTR_BIZ_CFG.PRIORITIES.map(s => `"${s}"`).join(',');
  const extra = MTTR_BIZ_CFG.EXTRA_JQL ? ` ${MTTR_BIZ_CFG.EXTRA_JQL} ` : '';
  const jql =
    `project = ${proj.key} AND statusCategory = Done${extra}` +
    ` AND (issuetype = ${typesIncident} OR (issuetype = ${typeBug} AND priority IN (${prios})))`;

  const res = mttr_computeAvgBusinessHours_(jql, MTTR_BIZ_CFG.FIELDS, MTTR_BIZ_CFG.PAGE_SIZE, MTTR_BIZ_CFG.WORK_START_HOUR, MTTR_BIZ_CFG.WORK_END_HOUR);
  // res = { avgHours: number, count: number }

  setMetric_(sheet, 'MTTR_hours', res.count > 0 ? res.avgHours : 0, '0.00');
  try { setMetric_(sheet, '# Incidents (MTTR scope)', res.count, '0'); } catch(_) {}

  ss.toast(`${proj.key}: MTTR (business)=${res.avgHours.toFixed(2)}h over ${res.count} incidents`, 'Jira Metrics (MTTR)', 6);
}

// ---- Core logic ----
function mttr_computeAvgBusinessHours_(jql, fields, pageSize, startHour, endHour) {
  let total = 0;
  let sumHours = 0;

  const tz = Session.getScriptTimeZone() || 'Etc/UTC';
  const url = `${jiraBase_()}/search/jql`;

  const body = {
    jql: String(jql || ''),
    fields: fields && fields.length ? fields : ['created','resolutiondate'],
    maxResults: Math.min(pageSize || 50, 100)
  };

  let pageToken = null;
  while (true) {
    if (pageToken) body.pageToken = pageToken; else delete body.pageToken;

    const data = httpJson_(url, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(body),
      muteHttpExceptions: true
    });

    if (!data || !Array.isArray(data.issues) || data.issues.length === 0) break;

    for (const issue of data.issues) {
      const created = issue.fields && issue.fields.created ? new Date(issue.fields.created) : null;
      const resolved = issue.fields && issue.fields.resolutiondate ? new Date(issue.fields.resolutiondate) : null;
      if (!created || !resolved) continue;

      const hrs = businessHoursDiff_(created, resolved, tz, startHour, endHour);
      if (hrs >= 0) {
        sumHours += hrs;
        total += 1;
      }
    }

    pageToken = data.nextPageToken || null;
    if (!pageToken) break;
  }

  return { avgHours: total > 0 ? sumHours / total : 0, count: total };
}

/** Business hours difference between two Date objects.
 * Counts only Mon–Fri, between [workStartHour, workEndHour).
 */
function businessHoursDiff_(startDate, endDate, tz, workStartHour, workEndHour) {
  if (endDate <= startDate) return 0;

  const msPerHour = 3600000;
  const workSpanHours = Math.max(0, (workEndHour - workStartHour));

  // Helper: clamp a Date to business window for that day
  function clampToWorkWindow_(d) {
    const y = Utilities.formatDate(d, tz, 'yyyy');
    const m = Utilities.formatDate(d, tz, 'MM');
    const dd = Utilities.formatDate(d, tz, 'dd');
    const H = Number(Utilities.formatDate(d, tz, 'HH'));
    const min = Utilities.formatDate(d, tz, 'mm');
    const s = Utilities.formatDate(d, tz, 'ss');

    const startStr = `${y}-${m}-${dd} ${String(workStartHour).padStart(2,'0')}:00:00`;
    const endStr   = `${y}-${m}-${dd} ${String(workEndHour).padStart(2,'0')}:00:00`;
    const dayStart = new Date(Utilities.formatDate(new Date(startStr), tz, "EEE, d MMM yyyy HH:mm:ss 'GMT'"));
    const dayEnd   = new Date(Utilities.formatDate(new Date(endStr),   tz, "EEE, d MMM yyyy HH:mm:ss 'GMT'"));

    if (d < dayStart) return dayStart;
    if (d > dayEnd)   return dayEnd;
    return d;
  }

  // Helper: is weekend
  function isWeekend_(d) {
    const day = Number(Utilities.formatDate(d, tz, 'u')); // 1..7 (Mon..Sun)
    return day >= 6; // 6=Sat, 7=Sun
  }

  // Move cursor through days
  let cursor = new Date(startDate);
  let end = new Date(endDate);
  let totalHours = 0;

  // If same day, compute overlap directly
  if (Utilities.formatDate(cursor, tz, 'yyyyMMdd') === Utilities.formatDate(end, tz, 'yyyyMMdd')) {
    if (isWeekend_(cursor)) return 0;
    const a = clampToWorkWindow_(cursor);
    const b = clampToWorkWindow_(end);
    const diff = Math.max(0, b.getTime() - a.getTime()) / msPerHour;
    return Math.min(diff, workSpanHours);
  }

  // First day partial
  if (!isWeekend_(cursor)) {
    const a = clampToWorkWindow_(cursor);
    const y = Utilities.formatDate(cursor, tz, 'yyyy');
    const m = Utilities.formatDate(cursor, tz, 'MM');
    const d = Utilities.formatDate(cursor, tz, 'dd');
    const endStr = `${y}-${m}-${d} ${String(workEndHour).padStart(2,'0')}:00:00`;
    const dayEnd = new Date(Utilities.formatDate(new Date(endStr), tz, "EEE, d MMM yyyy HH:mm:ss 'GMT'"));
    const diff = Math.max(0, dayEnd.getTime() - a.getTime()) / msPerHour;
    totalHours += Math.min(diff, workSpanHours);
  }

  // Move to next day 00:00
  cursor = new Date(cursor.getTime());
  cursor.setDate(cursor.getDate() + 1);
  cursor.setHours(0,0,0,0);

  // Iterate whole middle days
  while (Utilities.formatDate(cursor, tz, 'yyyyMMdd') < Utilities.formatDate(end, tz, 'yyyyMMdd')) {
    if (!isWeekend_(cursor)) totalHours += workSpanHours;
    cursor.setDate(cursor.getDate() + 1);
  }

  // Last day partial
  if (!isWeekend_(end)) {
    const y = Utilities.formatDate(end, tz, 'yyyy');
    const m = Utilities.formatDate(end, tz, 'MM');
    const d = Utilities.formatDate(end, tz, 'dd');
    const startStr = `${y}-${m}-${d} ${String(workStartHour).padStart(2,'0')}:00:00`;
    const dayStart = new Date(Utilities.formatDate(new Date(startStr), tz, "EEE, d MMM yyyy HH:mm:ss 'GMT'"));
    const b = clampToWorkWindow_(end);
    const diff = Math.max(0, b.getTime() - dayStart.getTime()) / msPerHour;
    totalHours += Math.min(diff, workSpanHours);
  }

  return totalHours;
}