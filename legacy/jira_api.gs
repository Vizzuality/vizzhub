function getProjectByKey_(key) {
  const url = `${jiraBase_()}/project/${encodeURIComponent(key)}`;
  const data = httpJson_(url);
  if (data && data.id) return { id: String(data.id), key: data.key, name: data.name };
  return null;
}

function fetchIssueCount_(jql) {
  // Jira Cloud: old /search endpoint is removed (410). Use /search/approximate-count with POST.
  // Base from jiraBase_() should already be .../rest/api/3
  const url = `${jiraBase_()}/search/approximate-count`;
  const body = { jql: String(jql || "") };

  // httpJson_ is assumed to accept UrlFetch options; send JSON body with POST
  const data = httpJson_(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });

  if (!data) return null;

  // Prefer new fields if present; fall back defensively.
  if (typeof data.approximateCount === "number") return data.approximateCount;
  if (typeof data.total === "number") return data.total; // some tenants may still mirror 'total'
  if (data.count && typeof data.count.value === "number") return data.count.value;

  return 0;
}
/**
 * Search Jira issues using the /search/jql endpoint with pagination.
 * @param {string} jql - The JQL query string.
 * @param {Array<string>} fields - List of fields to fetch for each issue.
 * @param {number} maxResults - Maximum total issues to return (will not exceed 100 per request).
 * @returns {Array<Object>} List of issues matching the query.
 */
function jiraSearchJql_(jql, fields, maxResults) {
  const url = `${jiraBase_()}/search/jql`;
  const body = {
    jql: String(jql || ""),
    fields: fields || ["id","key"],
    maxResults: Math.min(maxResults || 50, 100)
  };

  let results = [];
  let pageToken = null;
  do {
    if (pageToken) body.pageToken = pageToken;
    const data = httpJson_(url, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(body),
      muteHttpExceptions: true
    });
    if (!data || !data.issues) break;
    results = results.concat(data.issues);
    pageToken = data.nextPageToken || null;
  } while (pageToken && results.length < (maxResults || 50));

  return results;
}