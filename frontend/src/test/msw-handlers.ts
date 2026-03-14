import { http, HttpResponse } from 'msw';

// ---------------------------------------------------------------------------
// Default response fixtures — each handler returns a realistic baseline.
// Tests override individual handlers via server.use(...) for specific scenarios.
// ---------------------------------------------------------------------------

const BASE = '/api';

// -- Projects ---------------------------------------------------------------

const defaultProject = {
  id: 'project-123',
  name: 'Test Project',
  code: 'TST.001',
  program_id: null,
  program_name: null,
  is_billable: true,
  has_scorecard: true,
  has_dependabot_alerts: true,
  has_budget_alerts: true,
  currency: null,
  notes: null,
  summary: null,
  jira_project_key: 'TEST',
  github_repo: 'org/test-repo',
  slack_channel_id: null,
  start_date: '2026-01-01',
  end_date: null,
  status: 'live',
  finished_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
};

const defaultPaginatedProjects = {
  items: [defaultProject],
  total: 1,
  page: 1,
  page_size: 45,
  pages: 1,
};

// -- Scores -----------------------------------------------------------------

const defaultScores = {
  project_id: 'project-123',
  overall_score: 75.5,
  indicators: {
    spi: 0.95,
    cpi: 0.92,
    defect_density: 0.02,
    escaped_rate: 0.01,
    lead_time_days: 5,
    commitment_reliability: 0.85,
    pr_review_ratio: 0.95,
  },
  scores: {
    score: 82,
    dimensions: {
      p_time: 85,
      p_cost: 88,
      p_quality: 78,
      p_value: 75,
      p_satisfaction: 87,
      p_flow: 80,
      p_engineering: 82,
      p_risk: 90,
    },
    weights_applied: {},
    dora: null,
  },
};

// -- Config -----------------------------------------------------------------

const defaultConfig = {
  targets: {
    defect_density: 3,
    escaped_rate: 0.01,
    lead_time_days: 5,
  },
  weights: {
    global: {
      time: 0.12,
      cost: 0.1,
      quality: 0.18,
      value: 0.15,
      satisfaction: 0.12,
      flow: 0.15,
      engineering: 0.1,
      risk: 0.08,
    },
  },
  constants: {
    sev1_cap: 60,
    milestone_grace_days: 3,
  },
};

const defaultConfigParameters = {
  Targets: [
    {
      id: 1,
      category: 'Targets',
      name: 'DefDensity_t',
      value: '3.0000',
      unit: 'defects/100 tasks',
      notes: 'Target max defect density',
    },
  ],
  'Global Weights': [
    {
      id: 2,
      category: 'Global Weights',
      name: 'W_quality',
      value: '0.1800',
      unit: 'weight',
      notes: 'P_quality',
    },
  ],
};

// -- Metrics ----------------------------------------------------------------

const defaultMetrics = {
  id: 'metrics-1',
  project_id: 'project-123',
  period_start: '2026-01-01',
  period_end: '2026-01-15',
  period_year: 2026,
  period_month: 1,
  evm_data: {
    budget_total: 100000,
    cost_to_date: 50000,
    percent_completed: 50,
    percent_planned: 50,
  },
  milestones: [{ name: 'Phase 1', planned_date: '2026-02-01' }],
  jira_defects: {
    bugs_total: 10,
    tasks_completed: 100,
    escaped_defects: 2,
    incidents_count: 1,
  },
  flow_metrics: { total_stories: 50, stories_with_reviewer: 45 },
  github_metrics: {
    prs_without_review: 2,
    total_merged_prs: 30,
    high_severity_vulns: 0,
  },
  test_maturity: { e2e: 80, unit: 90 },
  architecture: {
    docs_up_to_date: true,
    iac_implemented: true,
    adrs_maintained: true,
    diagrams_updated: true,
  },
  pm_satisfaction: {
    delivery_complaints: 'no',
    design_complaints: 'no',
    overall_estimation: 85,
  },
  client_survey: { understanding: 90, proactivity: 85 },
  strategic_impact: 'high',
  governance_exceptions: 1,
  sev1_incident: false,
  created_at: '2026-01-15T12:00:00Z',
};

// -- Jobs -------------------------------------------------------------------

const defaultJob = {
  id: 'job-1',
  project_id: 'project-123',
  status: 'completed',
  job_type: 'capture_history',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:05:00Z',
  result: null,
  error: null,
};

// -- Notifications ----------------------------------------------------------

const defaultNotification = {
  id: 1,
  project_id: 'project-123',
  project_name: 'Test Project',
  alert_definition_id: 1,
  alert_name: 'SPI Below Target',
  channel: 'slack',
  sent_at: '2026-01-15T10:00:00Z',
  dismissed: false,
};

const defaultPaginatedNotifications = {
  items: [defaultNotification],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
};

// -- Alert Definitions ------------------------------------------------------

const defaultAlertDefinition = {
  id: 1,
  name: 'SPI Below Target',
  metric: 'spi',
  condition: 'below',
  threshold: 0.8,
  enabled: true,
  channels: ['slack'],
  cooldown_minutes: 60,
};

// -- Scheduled Jobs ---------------------------------------------------------

const defaultScheduledJob = {
  name: 'check_business_alerts',
  schedule: '0 9 * * 1-5',
  next_run: '2026-01-16T09:00:00Z',
  last_run: '2026-01-15T09:00:00Z',
  enabled: true,
};

// -- Silences ---------------------------------------------------------------

const defaultSilence = {
  id: 1,
  alert_definition_id: 1,
  project_id: 'project-123',
  reason: 'Known issue',
  created_by: 'admin@test.com',
  starts_at: '2026-01-15T00:00:00Z',
  expires_at: '2026-01-22T00:00:00Z',
};

// -- Global Metrics ---------------------------------------------------------

const defaultGlobalRecord = {
  year: 2026,
  month: 1,
  project_count: 5,
  avg_score: 78.5,
  dimension_averages: {
    p_time: 80,
    p_cost: 75,
    p_quality: 82,
    p_value: 70,
    p_satisfaction: 85,
    p_flow: 77,
    p_engineering: 80,
    p_risk: 79,
  },
  calculated_at: '2026-01-31T12:00:00Z',
};

// -- Integrations (Slack channels) ------------------------------------------

const defaultIntegrationsStatus = {
  jira: { connected: true, expires_at: null, token_type: 'oauth2', site_url: 'https://test.atlassian.net', created_at: '2026-01-01T00:00:00Z' },
  google_workspace: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  github: { connected: true, expires_at: null, token_type: 'pat', site_url: null, created_at: '2026-01-01T00:00:00Z' },
  slack: { connected: true, expires_at: null, token_type: 'bot', site_url: null, created_at: '2026-01-01T00:00:00Z' },
  slack_settings: { leadership_channel_id: 'C123' },
};

const defaultSlackChannels = [
  { id: 'C123', name: 'general' },
  { id: 'C456', name: 'alerts' },
];

// -- Auth -------------------------------------------------------------------

const defaultAuthUser = {
  id: 'user-1',
  email: 'admin@test.com',
  role: 'admin',
};

// ===========================================================================
// Handlers
// ===========================================================================

export const handlers = [
  // Projects
  http.get(`${BASE}/projects`, ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.get('lightweight') === 'true') {
      return HttpResponse.json([{ id: 'project-123', name: 'Test Project' }]);
    }
    const page = Number(url.searchParams.get('page') ?? '1');
    return HttpResponse.json({ ...defaultPaginatedProjects, page });
  }),

  http.get(`${BASE}/projects/:id`, ({ params }) => {
    return HttpResponse.json({ ...defaultProject, id: params.id });
  }),

  http.post(`${BASE}/projects`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json(
      { ...defaultProject, id: 'new-project-id', ...body },
      { status: 201 },
    );
  }),

  http.patch(`${BASE}/projects/:id`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultProject, id: params.id, ...body });
  }),

  http.put(`${BASE}/projects/:id`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultProject, id: params.id, ...body });
  }),

  http.delete(`${BASE}/projects/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Scores
  http.get(`${BASE}/scores/project/:projectId`, ({ params }) => {
    return HttpResponse.json({ ...defaultScores, project_id: params.projectId });
  }),

  http.get(`${BASE}/scores/project/:projectId/history`, ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get('limit') ?? '10');
    const history = Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
      ...defaultScores,
      scores: {
        ...defaultScores.scores,
        score: 75 - i * 2,
      },
    }));
    return HttpResponse.json(history);
  }),

  http.post(`${BASE}/scores/batch`, () => {
    return HttpResponse.json({
      scores: { 'project-123': defaultScores },
      errors: {},
    });
  }),

  // Config
  http.get(`${BASE}/config`, () => {
    return HttpResponse.json(defaultConfig);
  }),

  http.get(`${BASE}/config/parameters`, () => {
    return HttpResponse.json(defaultConfigParameters);
  }),

  http.get(`${BASE}/config/validate`, () => {
    return HttpResponse.json({ valid: true, groups: {}, errors: [] });
  }),

  http.patch(`${BASE}/config/parameters`, () => {
    return HttpResponse.json({ message: 'Parameters updated successfully' });
  }),

  // Metrics
  http.get(`${BASE}/metrics/project/:projectId`, () => {
    return HttpResponse.json([defaultMetrics]);
  }),

  http.post(`${BASE}/metrics/project/:projectId`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultMetrics, ...body });
  }),

  // Jobs
  http.get(`${BASE}/jobs`, () => {
    return HttpResponse.json([defaultJob]);
  }),

  http.get(`${BASE}/jobs/:jobId`, ({ params }) => {
    return HttpResponse.json({ ...defaultJob, id: params.jobId });
  }),

  http.post(`${BASE}/jobs/capture-history`, () => {
    return HttpResponse.json({ ...defaultJob, id: 'new-job-id', status: 'pending' });
  }),

  http.post(`${BASE}/jobs/:jobId/cancel`, ({ params }) => {
    return HttpResponse.json({ ...defaultJob, id: params.jobId, status: 'cancelled' });
  }),

  http.post(`${BASE}/jobs/:jobId/retry`, ({ params }) => {
    return HttpResponse.json({ ...defaultJob, id: params.jobId, status: 'pending' });
  }),

  http.delete(`${BASE}/jobs/:jobId`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Notifications
  http.get(`${BASE}/notifications`, () => {
    return HttpResponse.json(defaultPaginatedNotifications);
  }),

  http.get(`${BASE}/notifications/stats`, () => {
    return HttpResponse.json({ total: 10, unread: 3 });
  }),

  // Silences
  http.get(`${BASE}/silences`, () => {
    return HttpResponse.json([defaultSilence]);
  }),

  http.post(`${BASE}/silences`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultSilence, id: 2, ...body }, { status: 201 });
  }),

  http.put(`${BASE}/silences/:id`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultSilence, id: Number(params.id), ...body });
  }),

  http.delete(`${BASE}/silences/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Alert Definitions (admin)
  http.get(`${BASE}/admin/alerts`, () => {
    return HttpResponse.json([defaultAlertDefinition]);
  }),

  http.put(`${BASE}/admin/alerts/:id`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...defaultAlertDefinition, id: Number(params.id), ...body });
  }),

  http.post(`${BASE}/admin/alerts/:id/test`, () => {
    return HttpResponse.json({ success: true, message: 'Alert sent' });
  }),

  http.get(`${BASE}/admin/alerts/:alertId/templates`, () => {
    return HttpResponse.json([
      { id: 1, alert_definition_id: 1, channel: 'slack', template: 'Alert: {{metric}}' },
    ]);
  }),

  http.put(`${BASE}/admin/templates/:id`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: Number(params.id), ...body });
  }),

  // Scheduled Jobs (admin)
  http.get(`${BASE}/admin/jobs/scheduled`, () => {
    return HttpResponse.json([defaultScheduledJob]);
  }),

  http.post(`${BASE}/admin/jobs/scheduled/:jobName/run`, () => {
    return HttpResponse.json({ triggered: true, job_name: 'check_business_alerts' });
  }),

  // Global Metrics
  http.get(`${BASE}/global/:year/:month`, () => {
    return HttpResponse.json(defaultGlobalRecord);
  }),

  http.get(`${BASE}/global/history`, ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get('limit') ?? '12');
    const records = Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
      ...defaultGlobalRecord,
      month: 1 + i,
    }));
    return HttpResponse.json({ records });
  }),

  http.get(`${BASE}/global/available-months`, () => {
    return HttpResponse.json([
      { year: 2026, month: 1 },
      { year: 2025, month: 12 },
    ]);
  }),

  http.post(`${BASE}/global/calculate`, () => {
    return HttpResponse.json({
      year: 2026,
      month: 1,
      projects_processed: 5,
      record: defaultGlobalRecord,
    });
  }),

  http.post(`${BASE}/global/recalculate`, () => {
    return HttpResponse.json({
      year: 2026,
      month: 1,
      projects_processed: 5,
      record: defaultGlobalRecord,
    });
  }),

  // Integrations
  http.get(`${BASE}/admin/integrations/status`, () => {
    return HttpResponse.json(defaultIntegrationsStatus);
  }),

  http.get(`${BASE}/admin/integrations/slack/channels`, () => {
    return HttpResponse.json(defaultSlackChannels);
  }),

  http.post(`${BASE}/admin/integrations/slack/test`, () => {
    return HttpResponse.json({ ok: true, team: 'TestTeam', bot_id: 'B123' });
  }),

  // Auth — AuthContext uses raw fetch with full URLs, not axios with relative paths.
  // Handlers must use the full origin to match.
  http.get('http://localhost:8000/api/auth/me', () => {
    return HttpResponse.json(defaultAuthUser);
  }),

  http.post('http://localhost:8000/api/auth/google', () => {
    return HttpResponse.json({ user: defaultAuthUser });
  }),

  http.post('http://localhost:8000/api/auth/logout', () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
  }),
];

// Export fixtures for direct assertion in tests
export const fixtures = {
  project: defaultProject,
  paginatedProjects: defaultPaginatedProjects,
  scores: defaultScores,
  config: defaultConfig,
  configParameters: defaultConfigParameters,
  metrics: defaultMetrics,
  job: defaultJob,
  notification: defaultNotification,
  paginatedNotifications: defaultPaginatedNotifications,
  alertDefinition: defaultAlertDefinition,
  scheduledJob: defaultScheduledJob,
  silence: defaultSilence,
  globalRecord: defaultGlobalRecord,
  integrationsStatus: defaultIntegrationsStatus,
  slackChannels: defaultSlackChannels,
  authUser: defaultAuthUser,
};
