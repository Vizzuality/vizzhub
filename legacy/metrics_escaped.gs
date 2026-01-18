function esc_updateEscapedDefects() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Data_Forms");
  if (!sheet) return;

  const key = String(sheet.getRange("B2").getValue() || "").trim();
  if (!key) return;

  const jqlEscaped = `project = ${key} AND issuetype = Bug AND cf[10231] IN ("staging","production")`;
  const jqlTasks   = `project = ${key} AND issuetype IN (Story, Task, Bug) AND statusCategory = Done`;

  const escaped = jiraSearchJql_(jqlEscaped, ["id"], 1000).length;
  const tasks   = jiraSearchJql_(jqlTasks, ["id"], 1000).length;
  const rate100 = tasks > 0 ? (escaped / tasks) * 100 : 0;

  setMetric_(sheet, "EscapedRate_per_100Tasks (project total)", rate100, "0.00");
  setMetric_(sheet, "# Escaped defects (Staging + Production)", escaped, "0");

  ss.toast(`${key}: escaped=${escaped}, tasks=${tasks}, rate/100=${rate100.toFixed(2)}`, "Jira Metrics (Escaped)", 5);
}