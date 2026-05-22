export const Action = {
  SCORECARD_VIEW: 'scorecard:view',
  SCORECARD_EDIT_METRICS: 'scorecard:edit_metrics',
  SCORECARD_CAPTURE: 'scorecard:capture',
  SCORECARD_MANAGE: 'scorecard:manage',

  TRACKER_VIEW: 'tracker:view',
  TRACKER_MANAGE_OWN_REPORTS: 'tracker:manage_own_reports',
  TRACKER_MANAGE_ALL_REPORTS: 'tracker:manage_all_reports',
  TRACKER_MANAGE: 'tracker:manage',

  ISO_VIEW: 'iso:view',
  ISO_MANAGE: 'iso:manage',

  PROJECTS_VIEW: 'projects:view',
  PROJECTS_MANAGE: 'projects:manage',

  PLAYBOOK_EDIT: 'playbook:edit',

  ISO_DOCS_EDIT: 'iso_docs:edit',

  EVENTS_VIEW: 'events:view',
  EVENTS_MANAGE: 'events:manage',

  DEVSTACK_VIEW: 'devstack:view',
  DEVSTACK_MANAGE: 'devstack:manage',

  CAPACITY_VIEW: 'capacity:view',
  CAPACITY_MANAGE: 'capacity:manage',

  ACCRUAL_VIEW: 'accrual:view',
  ACCRUAL_MANAGE: 'accrual:manage',
  ACCRUAL_PERIOD_MANAGE: 'accrual:period_manage',

  ADMIN_USERS: 'admin:users',
  ADMIN_JOBS: 'admin:jobs',
  ADMIN_INTEGRATIONS: 'admin:integrations',
} as const;

export type Permission = typeof Action[keyof typeof Action];
