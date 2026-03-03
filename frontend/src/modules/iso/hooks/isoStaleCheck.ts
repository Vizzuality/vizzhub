const STALE_DAYS = 35;
const STALE_MS = STALE_DAYS * 24 * 60 * 60 * 1000;

export function isSnapshotStale(capturedAt: string | null): boolean {
  if (!capturedAt) {
    return true;
  }
  return Date.now() - new Date(capturedAt).getTime() > STALE_MS;
}
