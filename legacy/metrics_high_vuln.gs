// --- GitHub High Severity Vulnerabilities (>30d open) ---
// Counts Dependabot alerts with severity >= "high" that remain open >30 days.
// If Dependabot is disabled or inaccessible, assigns a strongly negative fallback (99)
// and writes the reason to C148.

function ghDepAlertsEnabled_(owner, repo) {
  var url = 'https://api.github.com/repos/' + encodeURIComponent(owner) + '/' + encodeURIComponent(repo) + '/vulnerability-alerts';
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: ghHeaders_(),
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  // 204 means enabled, 404/403 means disabled or no access
  return code === 204;
}

function ghListVulnerabilities_(owner, repo, max) {
  var out = [];
  var per = 100;
  var page = 1;
  var limit = Math.max(1, Math.min(1000, max || 500));

  while (out.length < limit) {
    var url = 'https://api.github.com/repos/' + encodeURIComponent(owner) + '/' + encodeURIComponent(repo) +
              '/dependabot/alerts?state=open&per_page=' + per + '&page=' + page;
    var resp = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: ghHeaders_(),
      muteHttpExceptions: true
    });
    var code = resp.getResponseCode();

    if (code === 403 || code === 404) {
      var body = resp.getContentText();
      if (body && body.indexOf('Dependabot alerts are disabled') !== -1) {
        throw new Error('DEPENDABOT_DISABLED');
      }
      throw new Error('GitHub HTTP ' + code + ' → ' + url + '\n' + body);
    }

    if (code < 200 || code >= 300) {
      throw new Error('GitHub HTTP ' + code + ' → ' + url + '\n' + resp.getContentText());
    }

    var data = JSON.parse(resp.getContentText());
    if (!data || !data.length) break;

    for (var i = 0; i < data.length && out.length < limit; i++) {
      out.push(data[i]);
    }

    if (data.length < per) break;
    page++;
  }

  return out;
}

function ghCountHighVulnOver30d_(owner, repo) {
  var list = ghListVulnerabilities_(owner, repo, 500);
  var now = new Date();
  var thresholdMs = 30 * 24 * 60 * 60 * 1000;
  var count = 0;

  for (var i = 0; i < list.length; i++) {
    var v = list[i];
    if (!v || !v.security_advisory) continue;

    var sev = String(v.security_advisory.severity || '').toLowerCase();
    if (sev !== 'high' && sev !== 'critical') continue;
    if (v.dismissed_at || v.fixed_at) continue;

    var created = v.created_at ? new Date(v.created_at) : null;
    if (created && (now - created) > thresholdMs) count++;
  }

  return count;
}

/**
 * Entry point: reads repo from Data_Forms!B3,
 * writes:
 *   B148 = count (or 99 fallback)
 *   C148 = status message
 */
function updateHighVulnOpenGt30d() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var forms = ss.getSheetByName('Data_Forms');
  if (!forms) throw new Error('Sheet "Data_Forms" not found');

  var slug = String(forms.getRange('B3').getValue() || '').trim();
  if (!slug || slug.indexOf('/') < 0) throw new Error('Set repo in Data_Forms!B3 as "owner/repo"');
  var parts = slug.split('/');
  var owner = parts[0].trim();
  var repo = parts[1].trim();

  var valCell = forms.getRange('B158');
  var msgCell = forms.getRange('C158');
  msgCell.clearContent();

  try {
    var enabled = ghDepAlertsEnabled_(owner, repo);

    if (!enabled) {
      valCell.setValue(99);
      msgCell.setValue('Dependabot disabled or inaccessible — HIGH RISK');
      SpreadsheetApp.flush();
      return;
    }

    var count = ghCountHighVulnOver30d_(owner, repo);
    valCell.setValue(count);
    msgCell.setValue(count === 0 ? 'No high vulns >30d' : count + ' high vulns >30d');
  }
  catch (e) {
    valCell.setValue(99);
    msgCell.setValue('Error fetching Dependabot data — HIGH RISK');
  }

  SpreadsheetApp.flush();
}