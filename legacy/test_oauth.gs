function getOAuthService() {
  return OAuth2.createService('Jira')
    .setAuthorizationBaseUrl('https://auth.atlassian.com/authorize')
    .setTokenUrl('https://auth.atlassian.com/oauth/token')
    .setClientId(PropertiesService.getScriptProperties().getProperty('JIRA_CLIENT_ID'))
    .setClientSecret(PropertiesService.getScriptProperties().getProperty('JIRA_CLIENT_SECRET'))
    .setCallbackFunction('authCallback')
    .setPropertyStore(PropertiesService.getUserProperties())
    .setScope('read:jira-work read:jira-user offline_access')
    .setParam('audience', 'api.atlassian.com');
}

function authorize() {
  const s = getOAuthService();
  if (s.hasAccess()) {
    Logger.log('✅ Already authorized');
  } else {
    Logger.log('🔗 Open and approve: %s', s.getAuthorizationUrl());
  }
}

function authCallback(request) {
  const ok = getOAuthService().handleCallback(request);
  return HtmlService.createHtmlOutput(ok ? 'OK, you can close this tab.' : 'Denied.');
}

function cmd_diagTokens() {
  var base = jiraBase_();
  var me = httpJson_(base + '/myself', { method: 'get' });
  Logger.log('myself ok? %s', me && me.accountId ? 'YES' : me);

  var agile = base.replace('/rest/api/3', '/rest/agile/1.0');
  var boards = httpJson_(agile + '/board?maxResults=1', { method: 'get' });
  Logger.log('agile ok? %s', boards && boards.values ? 'YES' : boards);
}

function diagForceRefreshAndLogScopes() {
  const sp = PropertiesService.getScriptProperties();
  sp.deleteProperty('JIRA_ACCESS_TOKEN'); // fuerza refresh limpio
  const data = refreshAccessToken_();     // usa el JIRA_REFRESH_TOKEN de la librería
  Logger.log('refreshAccessToken_ → code=OK scope="%s"', data && data.scope);
}

function diagAgileBoards() {
  const base = jiraBase_();
  const agile = base.replace('/rest/api/3', '/rest/agile/1.0');
  const res = httpJson_(agile + '/board?maxResults=1', { method: 'get' });
  Logger.log('Agile /board → %s', res && res.values ? 'OK' : JSON.stringify(res));
}