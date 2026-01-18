// --- GitHub PR review stats ---
// Populates both P_risk (PRsWithoutReview_count) and P_engineering (PR_review_ratio_0to1)
// Requires: GITHUB_TOKEN (Bearer token with repo + security_events scopes)

function ghToken_() {
  var t = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!t) throw new Error('Missing GITHUB_TOKEN in Script Properties');
  return t.trim();
}

function ghHeaders_() {
  return {
    Authorization: 'Bearer ' + ghToken_(),
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function ghFetchJson_(url) {
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: ghHeaders_(),
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300)
    throw new Error('GitHub HTTP ' + code + ' → ' + url + '\n' + resp.getContentText());
  return JSON.parse(resp.getContentText());
}

function ghListClosedMergedPRs_(owner, repo, max) {
  var out = [];
  var per = 100, page = 1;
  var limit = Math.max(1, Math.min(5000, max || 2000));
  while (out.length < limit) {
    var url = 'https://api.github.com/repos/' + encodeURIComponent(owner) + '/' +
              encodeURIComponent(repo) + '/pulls?state=closed&per_page=' + per + '&page=' + page;
    var data = ghFetchJson_(url) || [];
    if (!data.length) break;
    for (var i = 0; i < data.length && out.length < limit; i++) {
      if (data[i] && data[i].merged_at) out.push(data[i]);
    }
    if (data.length < per) break;
    page++;
  }
  return out;
}

function ghListReviews_(owner, repo, prNumber) {
  var url = 'https://api.github.com/repos/' + encodeURIComponent(owner) + '/' +
            encodeURIComponent(repo) + '/pulls/' + prNumber + '/reviews?per_page=100';
  return ghFetchJson_(url) || [];
}

function ghTargetBranches_() {
  var prop = (PropertiesService.getScriptProperties().getProperty('GITHUB_REVIEW_BRANCHES') || '').trim();
  return (prop ? prop.split(',') : ['dev','develop'])
         .map(function(s){ return s.trim().toLowerCase(); });
}

/**
 * Computes review stats in one pass:
 * Returns { totalMerged, mergedWithReview, mergedWithoutReview }
 */
function ghPRReviewStats_(owner, repo) {
  var prs = ghListClosedMergedPRs_(owner, repo, 2000);
  var targets = ghTargetBranches_();
  var total = 0, withReview = 0, withoutReview = 0;

  for (var i = 0; i < prs.length; i++) {
    var pr = prs[i];
    var baseRef = (pr.base && pr.base.ref) ? String(pr.base.ref).toLowerCase() : '';
    if (targets.indexOf(baseRef) === -1) continue;

    total++;
    var reviews = ghListReviews_(owner, repo, pr.number);
    if (reviews && reviews.length > 0) withReview++;
    else withoutReview++;
  }

  return { totalMerged: total, mergedWithReview: withReview, mergedWithoutReview: withoutReview };
}

/**
 * Main entry point:
 * Reads repo from Data_Forms!B3 ("owner/repo")
 * Writes:
 *   B138 = PRsWithoutReview_count
 *   B139 = PRsMerged_total
 *   B148 = PR_review_ratio_0to1
 *   B149 = PRsMerged_total (same)
 */
function updatePRReviewStats() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('Data_Forms');
  if (!sh) throw new Error('Sheet "Data_Forms" not found');

  var slug = String(sh.getRange('B3').getValue() || '').trim();
  if (!slug || slug.indexOf('/') < 0)
    throw new Error('Set repo in Data_Forms!B3 as "owner/repo"');
  var parts = slug.split('/');
  var owner = parts[0].trim(), repo = parts[1].trim();

  var stats = ghPRReviewStats_(owner, repo);
  var ratio = stats.totalMerged ? (stats.mergedWithReview / stats.totalMerged) : 0;

  sh.getRange('B138').setValue(stats.mergedWithoutReview);
  sh.getRange('B139').setValue(stats.totalMerged);
  sh.getRange('B148').setNumberFormat('0.00').setValue(ratio);
  sh.getRange('B149').setValue(stats.totalMerged);
}