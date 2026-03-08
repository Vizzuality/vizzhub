import type { DiffSummary, SnapshotSummary } from '@/modules/iso/types/iso';

export function formatChangeDetails(
  previousValue: Record<string, unknown> | null,
  currentValue: Record<string, unknown> | null,
): string {
  const parts: string[] = [];
  if (previousValue) {
    parts.push(`Previous: ${JSON.stringify(previousValue)}`);
  }
  if (currentValue) {
    parts.push(`Current: ${JSON.stringify(currentValue)}`);
  }
  return parts.join(' | ') || '\u2014';
}

export function getChangeTypeBadgeClasses(changeType: string): string {
  switch (changeType) {
    case 'new_user':
    case 'new_external':
      return 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800';
    case 'removed_user':
    case 'removed_external':
      return 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800';
    case 'role_change':
    case 'group_membership_change':
      return 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800';
    default:
      return '';
  }
}

export function formatChangeType(changeType: string): string {
  return changeType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function buildDiffStatItems(
  diffSummary: DiffSummary,
): { label: string; value: number }[] {
  const items = [
    { label: 'New Users', value: diffSummary.new_user },
    { label: 'Removed Users', value: diffSummary.removed_user },
    { label: 'Role Changes', value: diffSummary.role_change },
    { label: 'New External', value: diffSummary.new_external },
    { label: 'Group Changes', value: diffSummary.group_membership_change },
  ];
  if (diffSummary.removed_external) {
    items.push({ label: 'Removed External', value: diffSummary.removed_external });
  }
  return items;
}

export function buildSummaryStatItems(
  summary: SnapshotSummary,
  provider?: string,
): { label: string; value: number }[] {
  if (provider === 'github') {
    return [
      { label: 'Total Members', value: summary.total_members ?? 0 },
      { label: 'Owners', value: summary.total_admins ?? 0 },
      { label: 'Teams', value: summary.total_teams ?? 0 },
      { label: 'Outside Collaborators', value: summary.outside_collaborators ?? 0 },
    ];
  }
  return [
    { label: 'Total Users', value: summary.total_users ?? 0 },
    { label: 'Total Admins', value: summary.total_admins ?? 0 },
    { label: 'Total Groups', value: summary.total_groups ?? 0 },
    { label: 'External Members', value: summary.external_members ?? 0 },
  ];
}
