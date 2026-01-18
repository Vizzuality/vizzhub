function jiraBase_() {
  // Prefer aggregator with CLOUD_ID. Look in CONFIG, then Script/Document Properties.
  var cfgCloud = (typeof CONFIG !== 'undefined' && CONFIG.CLOUD_ID) ? String(CONFIG.CLOUD_ID).trim() : '';
  var sp = PropertiesService.getScriptProperties();
  var dp = PropertiesService.getDocumentProperties ? PropertiesService.getDocumentProperties() : null;
  var propCloud = (sp && (sp.getProperty('CLOUD_ID') || sp.getProperty('JIRA_CLOUD_ID'))) ||
                  (dp && (dp.getProperty('CLOUD_ID') || dp.getProperty('JIRA_CLOUD_ID'))) || '';
  var cloudId = (cfgCloud || propCloud).trim();
  if (cloudId) {
    return 'https://api.atlassian.com/ex/jira/' + cloudId + '/rest/api/3';
  }

  // Fallback: direct tenant site. Look in CONFIG first, then properties.
  var cfgSite = (typeof CONFIG !== 'undefined' && (CONFIG.ATLASSIAN_SITE || CONFIG.ATLASSIAN_NET || CONFIG.SITE) || '').trim();
  var propSite = (sp && (sp.getProperty('ATLASSIAN_SITE') || sp.getProperty('JIRA_ATLASSIAN_SITE') || sp.getProperty('SITE'))) ||
                 (dp && (dp.getProperty('ATLASSIAN_SITE') || dp.getProperty('JIRA_ATLASSIAN_SITE') || dp.getProperty('SITE'))) || '';
  var site = (cfgSite || propSite).trim();
  if (site) {
    var base = site.indexOf('http') === 0 ? site : ('https://' + site);
    return base + '/rest/api/3';
  }

  throw new Error('Missing CLOUD_ID and ATLASSIAN_SITE. Set CONFIG.CLOUD_ID or Script Property CLOUD_ID/JIRA_CLOUD_ID.');
}

function httpJson_(url, options) {
  var defaultOpts = {
    method: 'get',
    headers: currentAuthHeaders_(),
    muteHttpExceptions: true
  };
  var opts = Object.assign({}, defaultOpts, options || {});
  opts.headers = Object.assign({}, defaultOpts.headers, (options && options.headers) || {});

  var res = UrlFetchApp.fetch(url, opts);
  var code = res.getResponseCode();
  var body = res.getContentText();

  // If unauthorized/forbidden, try a single refresh and retry once
  if ((code === 401 || code === 403) && refreshAccessToken_()) {
    try {
      // Rebuild headers with the fresh access token
      var refreshedHeaders = currentAuthHeaders_();
      var retryOpts = Object.assign({}, opts, { headers: Object.assign({}, opts.headers, refreshedHeaders) });
      res = UrlFetchApp.fetch(url, retryOpts);
      code = res.getResponseCode();
      body = res.getContentText();
    } catch (e) {
      console.error('Retry after refresh failed: ' + (e && e.stack || e));
    }
  }

  if (code >= 200 && code < 300) return body ? JSON.parse(body) : {};
  console.error('HTTP ' + code + ' → ' + url + '\n' + body);
  return null;
}

function currentAuthHeaders_() {
  var sp = PropertiesService.getScriptProperties();
  var dp = PropertiesService.getDocumentProperties ? PropertiesService.getDocumentProperties() : null;
  var up = PropertiesService.getUserProperties();

  var bearer = '';
  // 1) Access token explicitly stored in properties
  if (sp) bearer = (sp.getProperty('JIRA_ACCESS_TOKEN') || '').trim();
  if (!bearer && dp) bearer = (dp.getProperty('JIRA_ACCESS_TOKEN') || '').trim();
  if (!bearer && up) bearer = (up.getProperty('JIRA_ACCESS_TOKEN') || '').trim();

  // 2) If host exposes OAuth service, prefer it (auto-refresh handled by library)
  if (!bearer && typeof getOAuthService === 'function') {
    try {
      var svc = getOAuthService();
      if (svc && svc.hasAccess()) {
        bearer = svc.getAccessToken();
      }
    } catch (e) { /* ignore and fall back */ }
  }

  // 3) If still no token, attempt refresh via Script Properties (shared bot refresh token)
  if (!bearer) {
    var data = refreshAccessToken_();
    if (data && data.access_token) bearer = data.access_token;
  }

  if (bearer) return { Authorization: 'Bearer ' + bearer, Accept: 'application/json' };
  throw new Error('No Jira auth configured: provide OAuth service in host or set JIRA_CLIENT_ID/JIRA_CLIENT_SECRET/JIRA_REFRESH_TOKEN in Script Properties.');
}

function refreshAccessToken_() {
  try {
    var sp = PropertiesService.getScriptProperties();
    var clientId = (sp.getProperty('JIRA_CLIENT_ID') || '').trim();
    var clientSecret = (sp.getProperty('JIRA_CLIENT_SECRET') || '').trim();
    var refreshToken = (sp.getProperty('JIRA_REFRESH_TOKEN') || '').trim();

    if (!clientId || !clientSecret || !refreshToken) {
      return null; // Not enough info to refresh
    }

    var resp = UrlFetchApp.fetch('https://auth.atlassian.com/oauth/token', {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({
        grant_type: 'refresh_token',
        client_id: clientId,
        client_secret: clientSecret,
        refresh_token: refreshToken
      }),
      muteHttpExceptions: true
    });

    var code = resp.getResponseCode();
    var text = resp.getContentText();
    if (code !== 200) {
      console.error('Jira OAuth refresh failed HTTP ' + code + ': ' + text);
      return null;
    }
    var data = JSON.parse(text);
    if (data && data.access_token) {
      sp.setProperty('JIRA_ACCESS_TOKEN', data.access_token);
      if (data.refresh_token) {
        // Persist rotated refresh token
        sp.setProperty('JIRA_REFRESH_TOKEN', data.refresh_token);
      }
      return data;
    }
    return null;
  } catch (e) {
    console.error('refreshAccessToken_ error: ' + (e && e.stack || e));
    return null;
  }
}