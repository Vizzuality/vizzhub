const FE_DEFAULT_STATUSES = {
  start: {
    // IDs observed in your instance (To Do / New / Ready ...)
    ids: ['10025','10026','10027','10006'],
    names: ['NEW','READY TO DEVELOP','READY TO DISCUSS','TO DO']
  },
  end: {
    // Multiple "Done" IDs exist; include Declined
    ids: ['10005','10041','10054','10047'],
    names: ['DONE','DECLINED']
  },
  active: {
    // In progress variants + review/test/blocked
    ids: ['3','10068','10016','10020','10013'],
    names: ['IN PROGRESS','WORK IN PROGRESS','BLOCKED','CODE REVIEW','QC']
  }
};

// If true: startAt=created, endAt=resolutiondate, skip Start/End lookups
const FE_FAST_MODE = true;

// Build a Set-based structure like fe_loadStatusSets_ returns for "active"
function fe_defaultActiveSet_() {
  const ids = new Set();
  const names = new Set();
  (FE_DEFAULT_STATUSES.active.ids || []).forEach(v => ids.add(String(v)));
  (FE_DEFAULT_STATUSES.active.names || []).forEach(v => names.add(String(v).toUpperCase()));
  return { ids, names };
}

function fe_loadStatusSets_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  function readNamed(name) {
    try {
      const r = ss.getRangeByName(name);
      if (!r) return [];
      const vals = r.getNumRows() * r.getNumColumns() > 1 ? r.getValues().flat() : [r.getValue()];
      return vals.filter(v => v !== null && v !== '').map(String);
    } catch (e) {
      return [];
    }
  }
  function toSets(arr) {
    const ids = new Set();
    const names = new Set();
    arr.forEach(s => {
      String(s).split(',').forEach(tok => {
        const t = String(tok).trim();
        if (!t) return;
        if (/^\d+$/.test(t)) ids.add(t); else names.add(t.toUpperCase());
      });
    });
    return { ids, names };
  }
  function mergeInto(target, src) {
    if (!src) return target;
    if (src.ids)  src.ids.forEach(v => target.ids.add(String(v)));
    if (src.names) src.names.forEach(v => target.names.add(String(v).toUpperCase()));
    return target;
  }

  // Load from Params
  const startP  = toSets(readNamed('Flow_StartStatuses'));
  const endP    = toSets(readNamed('Flow_EndStatuses'));
  const activeP = toSets(readNamed('Flow_ActiveStatuses'));

  // If Params are empty, fall back to defaults. If partially filled, merge.
  const start  = mergeInto(startP,  (startP.ids.size || startP.names.size) ? null : FE_DEFAULT_STATUSES.start);
  const end    = mergeInto(endP,    (endP.ids.size   || endP.names.size)   ? null : FE_DEFAULT_STATUSES.end);
  const active = mergeInto(activeP, (activeP.ids.size|| activeP.names.size)? null : FE_DEFAULT_STATUSES.active);

  return { start, end, active };
}

function fe_isInSet_(id, name, set) {
  if (id && set.ids.has(String(id))) return true;
  if (name && set.names.has(String(name).toUpperCase())) return true;
  return false;
}

// Fetches the full status-change event history for a Jira issue, handling pagination.
function fe_fetchStatusEvents_(issueIdOrKey) {
  const events = [];
  let startAt = 0;
  const batch = 100;
  while (true) {
    const url = `${jiraBase_()}/issue/${issueIdOrKey}/changelog?startAt=${startAt}&maxResults=${batch}`;
    const resp = httpJson_(url, { method: 'get', muteHttpExceptions: true });
    if (!resp || !Array.isArray(resp.values) || resp.values.length === 0) break;
    for (const h of resp.values) {
      if (!Array.isArray(h.items)) continue;
      for (const it of h.items) {
        if (it && it.field === 'status') {
          events.push({ t: new Date(h.created), toId: String(it.to || ''), toName: String(it.toString || '') });
        }
      }
    }
    startAt += (resp.maxResults || resp.values.length);
    const total = (typeof resp.total === 'number') ? resp.total : startAt;
    if (startAt >= total) break;
  }
  events.sort((a,b) => a.t - b.t);
  return events;
}

function fe_firstTimeInStatuses_(issue, targetSet) {
  const events = fe_fetchStatusEvents_(issue.id || issue.key);
  if (!events.length) return null;
  let earliest = null;
  for (const e of events) {
    if (fe_isInSet_(e.toId, e.toName, targetSet)) {
      if (!earliest || e.t < earliest) earliest = e.t;
    }
  }
  return earliest;
}

/**
 * FlowEfficiency_0to1 (status-based):
 * Active work time / Total elapsed time (0–1), using business hours.
 * - Total = business hours between first entrance into any Start status and first entrance into any End status.
 * - Active = sum of business hours spent while the issue is in any Active status within [startAt, endAt].
 * Start/End/Active status sets are read from Params named ranges:
 *   Flow_StartStatuses, Flow_EndStatuses, Flow_ActiveStatuses (IDs or names, comma- or cell-separated).
 * Aggregation = sum(Active_i) / sum(Total_i) over recently closed issues.
 */

function updateFlowEfficiency() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const forms = ss.getSheetByName('Data_Forms');
  const data  = ss.getSheetByName('Data');
  if (!forms || !data) return;

  const projectKey = String(forms.getRange('B2').getValue() || '').trim();
  if (!projectKey) return;

  const cfg = {
    windowDays: 90,     // look-back window
    sampleMax: 200,     // max issues
    issueTypes: ['Story','Task','Bug']
  };

  const fe = fe_computeFlowEfficiency_(projectKey, cfg);
  if (fe == null) {
    forms.getRange('B120').clearContent();
  } else {
    forms.getRange('B120').setNumberFormat('0.00').setValue(fe);
  }

  ss.toast(`${projectKey} FlowEfficiency_0to1 = ${fe != null ? fe.toFixed(2) : '—'}`, 'Jira Metrics (Flow Efficiency)', 6);
}

function fe_computeFlowEfficiency_(projectKey, cfg) {
  const { windowDays, sampleMax, issueTypes } = cfg;
  const issueTypeList = issueTypes.map(s => `"${s}"`).join(',');
  const jql =
    `project = ${projectKey} AND issuetype IN (${issueTypeList}) ` +
    `AND statusCategory = Done AND resolutiondate >= -${windowDays}d ` +
    `ORDER BY resolutiondate DESC`;

  // Fast mode toggle
  const tz = Session.getScriptTimeZone() || 'Etc/UTC';
  const useFast = FE_FAST_MODE === true;
  const statusSets = useFast ? null : fe_loadStatusSets_();

  const url = `${jiraBase_()}/search/jql?expand=changelog`;
  const body = {
    jql,
    fields: ['key','issuetype','created','resolutiondate','status'],
    maxResults: Math.min(sampleMax, 100)
  };

  let collected = 0;
  let pageToken = null;
  let sumActiveH = 0;
  let sumTotalH  = 0;

  while (true) {
    if (pageToken) body.pageToken = pageToken; else delete body.pageToken;

    const resp = httpJson_(url, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(body),
      muteHttpExceptions: true
    });
    if (!resp || !Array.isArray(resp.issues) || resp.issues.length === 0) break;

    for (const issue of resp.issues) {
      if (collected >= sampleMax) break;

      const created  = issue.fields && issue.fields.created ? new Date(issue.fields.created) : null;
      const resolved = issue.fields && issue.fields.resolutiondate ? new Date(issue.fields.resolutiondate) : null;

      const startAt = useFast ? created  : (fe_firstTimeInStatuses_(issue, statusSets.start) || created);
      const endAt   = useFast ? resolved : (fe_firstTimeInStatuses_(issue, statusSets.end)   || resolved);

      if (startAt && endAt && endAt > startAt) {
        const totalH = businessHoursDiff_(startAt, endAt, tz, LT_BIZ_CFG.startHour, LT_BIZ_CFG.endHour);
        if (totalH >= 0) {
          const activeSet = useFast ? fe_defaultActiveSet_() : statusSets.active;
          const activeH = fe_activeHoursInActiveStatuses_(issue, activeSet, startAt, endAt, tz);
          if (activeH >= 0) {
            sumTotalH  += totalH;
            sumActiveH += Math.min(activeH, totalH);
          }
        }
      }

      collected++;
    }

    if (collected >= sampleMax) break;
    pageToken = resp.nextPageToken || null;
    if (!pageToken) break;
  }

  if (sumTotalH <= 0) return null;
  const ratio = sumActiveH / sumTotalH;
  return Math.max(0, Math.min(1, ratio));
}

// Sum business hours in statuses from explicit Active status set between start/end
function fe_activeHoursInActiveStatuses_(issue, activeSet, startAt, endAt, tz) {
  const events = fe_fetchStatusEvents_(issue.id || issue.key);
  if (!Array.isArray(events) || events.length === 0) { return 0; }

  let currId = null, currName = null;
  for (let i = 0; i < events.length; i++) {
    if (events[i].t <= startAt) { currId = events[i].toId; currName = events[i].toName; } else break;
  }

  let cursor = startAt;
  let activeH = 0;

  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.t <= startAt) continue;
    if (e.t > endAt) break;

    if (cursor < e.t) {
      if (fe_isInSet_(currId, currName, activeSet)) {
        const h = businessHoursDiff_(cursor, e.t, tz, LT_BIZ_CFG.startHour, LT_BIZ_CFG.endHour);
        if (h > 0) activeH += h;
      }
      cursor = e.t;
    }
    currId = e.toId; currName = e.toName;
  }

  if (cursor < endAt && fe_isInSet_(currId, currName, activeSet)) {
    const h = businessHoursDiff_(cursor, endAt, tz, LT_BIZ_CFG.startHour, LT_BIZ_CFG.endHour);
    if (h > 0) activeH += h;
  }

  return activeH;
}
