// metrics_commitment_reliability.gs — Minimal, clean version
// CommitmentReliability_0to1 (simple): ratio of issues that touched exactly 1 sprint
// over issues that touched ≥1 sprints within closed sprints of the project.
// Writes:
//   B128 = ratio (0..1, formatted 0.00)
//   C128 = committed (issues with ≥1 sprint)
//   D128 = completed-as-committed (issues with exactly 1 sprint)
//   E128 = multi-sprint (issues with >1 sprints)
//   F128 = 0 (reserved)


function updateCommitmentReliability() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var forms = ss.getSheetByName('Data_Forms');
  if (!forms) return;

  var projectKey = String(forms.getRange('B2').getValue() || '').trim();
  if (!projectKey) return;

  var result = cr_commitment_by_sprintHops_(projectKey) || {
    ratio: 0, committed: 0, completed: 0, multi: 0
  };

  forms.getRange('B128').setValue('Ratio');
  forms.getRange('C128').setValue('Committed(≥1 sprint)');
  forms.getRange('D128').setValue('Single-sprint');
  forms.getRange('E128').setValue('Multi-sprint');

  forms.getRange('B129').setNumberFormat('0.00').setValue(result.ratio);
  forms.getRange('C129').setValue(result.committed);
  forms.getRange('D129').setValue(result.completed);
  forms.getRange('E129').setValue(result.multi);
  forms.getRange('F129').setValue(0);
}


function cr_commitment_by_sprintHops_(projectKey) {
  var board = cr_firstScrumBoard_(projectKey);
  if (!board) return { ratio: 0, committed: 0, completed: 0, multi: 0 };

  var closed = cr_closedSprintsByBoard_(board.id);
  if (!closed.length) return { ratio: 0, committed: 0, completed: 0, multi: 0 };

  var touched = Object.create(null);

  for (var si = 0; si < closed.length; si++) {
    var s = closed[si];
    var list = cr_listSprintIssueKeys_JQL_(s.id, projectKey, 2000);
    var keys = list.keys;
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (!touched[k]) touched[k] = Object.create(null);
      touched[k][String(s.id)] = true;
    }
  }

  var committed = 0, single = 0, multi = 0;
  for (var k in touched) {
    var count = 0;
    var map = touched[k];
    for (var sid in map) count++;
    if (count >= 1) {
      committed++;
      if (count === 1) single++; else multi++;
    }
  }

  var ratio = committed ? (single / committed) : 0;
  if (ratio < 0) ratio = 0;
  if (ratio > 1) ratio = 1;

  return { ratio: ratio, committed: committed, completed: single, multi: multi };
}


function agileBase_() {
  return jiraBase_().replace('/rest/api/3', '/rest/agile/1.0');
}

function cr_firstScrumBoard_(projectKey) {
  var url = agileBase_() + '/board?projectKeyOrId=' + encodeURIComponent(projectKey) +
            '&type=scrum&maxResults=50';
  var resp = httpJson_(url, { method: 'get' });
  var boards = (resp && resp.values) || [];
  return boards.length ? boards[0] : null;
}

function cr_closedSprintsByBoard_(boardId) {
  var out = [];
  var startAt = 0;
  var batch = 50;
  while (true) {
    var url = agileBase_() + '/board/' + encodeURIComponent(boardId) +
              '/sprint?state=closed&startAt=' + startAt + '&maxResults=' + batch;
    var resp = httpJson_(url, { method: 'get' });
    var vals = (resp && resp.values) || [];
    for (var i = 0; i < vals.length; i++) out.push(vals[i]);
    if (!resp || vals.length === 0 || resp.isLast) break;
    startAt += (resp.maxResults || vals.length);
  }
  return out;
}

function cr_listSprintIssueKeys_JQL_(sprintId, projectKey, cap) {
  var out = [];
  var limit = Math.max(50, Math.min(2000, cap || 500));
  var url = jiraBase_() + '/search/jql';
  var maxResults = 100;
  var pageToken = null;
  var jql = 'sprint = ' + sprintId + (projectKey ? (' AND project = ' + projectKey) : '');

  while (out.length < limit) {
    var payload = { jql: jql, maxResults: maxResults };
    if (pageToken) payload.pageToken = pageToken;

    var resp = httpJson_(url, {
      method: 'post',
      payload: JSON.stringify(payload),
      contentType: 'application/json'
    });

    var issues = (resp && resp.issues) || [];
    for (var i = 0; i < issues.length; i++) {
      var key = issues[i].key || String(issues[i].id || '');
      if (key) out.push(key);
    }
    if (!issues.length || !resp || !resp.nextPageToken) break;
    pageToken = resp.nextPageToken;
  }
  return { keys: out };
}