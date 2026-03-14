const STATUS_LABELS: Record<string, string> = {
  proposal: 'Proposal',
  live: 'Live',
  finished: 'Finished',
};

export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
