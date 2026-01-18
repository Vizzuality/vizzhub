function jiraCountJql_(jql) {
  // Use the library pager that already works with /search/jql
  // Request only "id" to minimize payload; length is the count
  return jiraSearchJql_(jql, ["id"], 5000).length;
}

/**
 * Writes:
 *   Data_Forms!B179 = total "story" issues in Done
 *   Data_Forms!B180 = Done stories with NO reviewers
 *
 * JQLs (kept intentionally simple to match Jira UI results):
 *   base:      project = KEY AND type = 'story' AND status = 'Done'
 *   with rev.: base AND reviewers is not empty
 */
function updateStoriesReviewerCounts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName('Data_Forms');
  if (!sh) throw new Error('Sheet "Data_Forms" not found');

  var projectKey = String(sh.getRange('B2').getValue() || '').trim();
  if (!projectKey) throw new Error('Project key missing in Data_Forms!B2');

  var baseJql = "project = " + projectKey + " AND type = 'story' AND status = 'Done' ";
  var withReviewerJql = baseJql + " AND reviewers is not empty";

  var totalDone = jiraCountJql_(baseJql);
  var withReviewer = jiraCountJql_(withReviewerJql);

  sh.getRange('B179').setValue(totalDone);
  sh.getRange('B180').setValue(withReviewer);
}