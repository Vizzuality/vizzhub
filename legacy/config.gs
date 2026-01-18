// Central config (prefer Script Properties for non-secret parameters)
const CONFIG = {
  CLOUD_ID: "7ff2b411-09f5-4720-b9b3-83f3ca0eb926",
  ATLASSIAN_SITE: "vizzuality.atlassian.net", // legacy fallback only; OAuth uses CLOUD_ID
};

// NOTE: Authentication is handled via OAuth2 Bearer tokens.
// See http.gs → currentAuthHeaders_() which reads JIRA_ACCESS_TOKEN from Script/User Properties.

// Existing helper
function getProp_(key, fallback) {
  const v = PropertiesService.getScriptProperties().getProperty(key);
  return (v !== null && v !== undefined && v !== "") ? v : fallback;
}