/****
 * LeadTime_days: average days from first entrance into "To Do" (statusCategory=new)
 * to "Done" (resolutiondate or statusCategory=done), measured in business days (working hours) over a recent sample of completed issues.
 */

const LT_BIZ_CFG = {
  startHour: 9,  // business day start (local script timezone)
  endHour: 18    // business day end
};

function updateLeadTimeDays() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const forms = ss.getSheetByName('Data_Forms');
  const data  = ss.getSheetByName('Data');
  if (!forms || !data) return;

  const projectKey = String(forms.getRange('B2').getValue() || '').trim();
  if (!projectKey) return;

  const cfg = {
    windowDays: 90,     // look-back window
    sampleMax: 200,     // max issues to consider
    issueTypes: ['Story','Task','Bug']
  };

  const avgDays = lt_computeLeadTimeDays_(projectKey, cfg);
  if (avgDays == null) {
    forms.getRange('B111').clearContent();
  } else {
    forms.getRange('B111').setNumberFormat('0.00').setValue(avgDays);
  }

  ss.toast(`${projectKey} LeadTime_days = ${avgDays != null ? avgDays.toFixed(2) : '—'}`, 'Jira Metrics (Lead Time)', 6);
}

/**
 * Core calculation.
 */
function lt_computeLeadTimeDays_(projectKey, cfg) {
  const { windowDays, sampleMax, issueTypes } = cfg;
  const issueTypeList = issueTypes.map(s => `"${s}"`).join(',');
  const jql = `project = ${projectKey} AND issuetype IN (${issueTypeList}) AND statusCategory = Done AND resolutiondate >= -${windowDays}d ORDER BY resolutiondate DESC`;

  // Build status name -> category key map (e.g., "To Do", "In Progress", "Done")
  const statusCatByName = lt_fetchStatusCategories_(); // { "To Do": "new", "In Progress": "indeterminate", "Done": "done", ... }
  const tz = Session.getScriptTimeZone() || 'Etc/UTC';

  const url = `${jiraBase_()}/search/jql?expand=changelog`;
  const body = {
    jql,
    fields: ['key','issuetype','created','resolutiondate','status'],
    maxResults: Math.min(sampleMax, 100)
  };

  let collected = 0;
  let pageToken = null;
  let sumDays = 0;
  let count = 0;

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
      if (collected >= sampleMax) break;

      const created = issue.fields && issue.fields.created ? new Date(issue.fields.created) : null;
      const resolved = issue.fields && issue.fields.resolutiondate ? new Date(issue.fields.resolutiondate) : null;

      // START: first time the issue entered a status whose category is "new"
      const startAt = lt_firstTimeInCategoryNew_(issue, statusCatByName) || created;

      // END: resolutiondate preferred; otherwise first time into category "done"
      const endAt = resolved || lt_firstTimeInCategoryDone_(issue, statusCatByName);

      if (startAt && endAt && endAt >= startAt) {
        // Business hours between start/end, then convert to business days
        const hours = businessHoursDiff_(startAt, endAt, tz, LT_BIZ_CFG.startHour, LT_BIZ_CFG.endHour);
        if (hours >= 0) {
          const bizDayLen = Math.max(1, LT_BIZ_CFG.endHour - LT_BIZ_CFG.startHour); // avoid divide-by-zero
          const days = hours / bizDayLen;
          sumDays += days;
          count++;
        }
      }

      collected++;
    }

    if (collected >= sampleMax) break;
    pageToken = data.nextPageToken || null;
    if (!pageToken) break;
  }

  return count > 0 ? (sumDays / count) : null;
}

/**
 * Map status name -> statusCategory.key ("new" | "indeterminate" | "done")
 */
function lt_fetchStatusCategories_() {
  const url = `${jiraBase_()}/status`;
  const data = httpJson_(url, { method: 'get', muteHttpExceptions: true });
  const map = {};
  if (Array.isArray(data)) {
    for (const st of data) {
      if (st && st.name && st.statusCategory && st.statusCategory.key) {
        map[String(st.name)] = String(st.statusCategory.key); // e.g., "Done" -> "done"
      }
    }
  }
  return map;
}

/**
 * From issue.changelog, find the earliest timestamp when status became category "new".
 */
function lt_firstTimeInCategoryNew_(issue, statusCatByName) {
  return lt_firstTimeForCategory_(issue, statusCatByName, 'new');
}

/**
 * From issue.changelog, find the earliest timestamp when status became category "done".
 */
function lt_firstTimeInCategoryDone_(issue, statusCatByName) {
  return lt_firstTimeForCategory_(issue, statusCatByName, 'done');
}

function lt_firstTimeForCategory_(issue, statusCatByName, targetCatKey) {
  const cl = issue.changelog;
  if (!cl || !Array.isArray(cl.histories)) return null;

  // Each history has: created (timestamp), items[] with { field, fromString, toString }
  // We look for first item where field='status' and toString maps to targetCatKey.
  let earliest = null;
  for (const h of cl.histories) {
    if (!Array.isArray(h.items)) continue;
    for (const it of h.items) {
      if (it && it.field === 'status' && it.toString && statusCatByName[it.toString] === targetCatKey) {
        const t = new Date(h.created);
        if (!earliest || t < earliest) earliest = t;
      }
    }
  }
  return earliest;
}