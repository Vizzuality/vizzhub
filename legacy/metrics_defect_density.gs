function updateDefectDensity() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Data_Forms");
  if (!sheet) return;

  const key = String(sheet.getRange("B2").getValue() || "").trim();
  if (!key) return;

  const proj = getProjectByKey_(key);
  if (!proj) return;

  const projectKey = proj.key;
  const jqlBugs  = `project = ${projectKey} AND issuetype = Bug AND statusCategory = Done`;
  const jqlTasks = `project = ${projectKey} AND issuetype in (Story, Task, Bug) AND statusCategory = Done`;

  const bugsClosed     = jiraSearchJql_(jqlBugs, ["id"], 1000).length;
  const tasksCompleted = jiraSearchJql_(jqlTasks, ["id"], 1000).length;
  const density        = tasksCompleted > 0 ? (bugsClosed / tasksCompleted) * 100 : 0;

  setMetric_(sheet, "# Bugs closed", bugsClosed, "0");
  setMetric_(sheet, "# Tasks completed", tasksCompleted, "0");
  setMetric_(sheet, "DefectDensity_per_100Tasks", density, "0.00");

  ss.toast(`${proj.key}: bugs=${bugsClosed}, tasks=${tasksCompleted}, density=${density.toFixed(2)}`, "Jira Metrics", 6);
}