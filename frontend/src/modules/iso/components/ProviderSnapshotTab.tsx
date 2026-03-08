import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Download, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { PaginationControls } from '@/shared/components/ui/pagination-controls';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { ReviewStatusBadge } from '@/modules/iso/components/review-status-badge';
import type { AccessSnapshotSummary } from '@/modules/iso/types/iso';
import {
  useIsoSnapshots,
  useDeleteSnapshot,
  useCaptureSnapshot,
} from '@/modules/iso/hooks/useIso';
import { useIsoExport } from '@/modules/iso/hooks/useIsoExport';
import { isSnapshotStale } from '@/modules/iso/hooks/isoStaleCheck';
import { formatDate } from '@/utils/formatters';

interface ProviderSnapshotTabProps {
  readonly provider: string;
  readonly providerLabel: string;
  readonly isConnected: boolean;
  readonly page: number;
  readonly onPageChange: (page: number) => void;
}

interface ColumnDef {
  readonly header: string;
  readonly accessor: (snap: AccessSnapshotSummary) => number;
}

const PROVIDER_COLUMNS: Record<string, ColumnDef[]> = {
  google_workspace: [
    { header: 'Users', accessor: (s) => s.summary.total_users ?? 0 },
    { header: 'Admins', accessor: (s) => s.summary.total_admins ?? 0 },
    { header: 'Groups', accessor: (s) => s.summary.total_groups ?? 0 },
    { header: 'External', accessor: (s) => s.summary.external_members ?? 0 },
  ],
  github: [
    { header: 'Members', accessor: (s) => s.summary.total_members ?? 0 },
    { header: 'Admins', accessor: (s) => s.summary.total_admins ?? 0 },
    { header: 'Teams', accessor: (s) => s.summary.total_teams ?? 0 },
    { header: 'Outside Collab.', accessor: (s) => s.summary.outside_collaborators ?? 0 },
  ],
  jira: [
    { header: 'Users', accessor: (s) => s.summary.total_users ?? 0 },
    { header: 'Admins', accessor: (s) => s.summary.total_admins ?? 0 },
    { header: 'Groups', accessor: (s) => s.summary.total_groups ?? 0 },
    { header: 'External', accessor: (s) => s.summary.external_users ?? 0 },
  ],
};

export default function ProviderSnapshotTab({
  provider,
  providerLabel,
  isConnected,
  page,
  onPageChange,
}: ProviderSnapshotTabProps): JSX.Element {
  const { data, isLoading } = useIsoSnapshots({ provider, page, page_size: 20 });
  const deleteSnapshot = useDeleteSnapshot();
  const capture = useCaptureSnapshot();
  const { exportSnapshots, isExporting } = useIsoExport();

  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const [fromMonth, setFromMonth] = useState(currentMonth);
  const [fromYear, setFromYear] = useState(currentYear - 1);
  const [toMonth, setToMonth] = useState(currentMonth);
  const [toYear, setToYear] = useState(currentYear);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const handleDelete = (e: React.MouseEvent): void => {
    e.preventDefault();
    if (!deleteTargetId) return;
    deleteSnapshot.mutate(deleteTargetId, {
      onSettled: () => setDeleteTargetId(null),
    });
  };

  const totalPages = data?.pages ?? 0;
  const firstSnapshot = data?.items?.[0];
  const lastCaptureDate = firstSnapshot?.captured_at ?? null;
  const isStale = isSnapshotStale(lastCaptureDate);
  const columns = PROVIDER_COLUMNS[provider] ?? PROVIDER_COLUMNS.google_workspace;

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-4">
      {isStale && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-950">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {lastCaptureDate
              ? `Last ${providerLabel} snapshot is over 35 days old. Consider capturing a new snapshot.`
              : `No ${providerLabel} snapshots yet. Capture your first snapshot to begin access reviews.`}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {lastCaptureDate
            ? `Last capture: ${formatDate(lastCaptureDate)}`
            : 'No snapshots yet'}
        </p>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <Select value={String(fromMonth)} onValueChange={(v) => setFromMonth(Number(v))}>
              <SelectTrigger className="w-20" aria-label="From month">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {String(m).padStart(2, '0')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(fromYear)} onValueChange={(v) => setFromYear(Number(v))}>
              <SelectTrigger className="w-24" aria-label="From year">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">&ndash;</span>
            <Select value={String(toMonth)} onValueChange={(v) => setToMonth(Number(v))}>
              <SelectTrigger className="w-20" aria-label="To month">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {String(m).padStart(2, '0')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(toYear)} onValueChange={(v) => setToYear(Number(v))}>
              <SelectTrigger className="w-24" aria-label="To year">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              const from = `${fromYear}-${String(fromMonth).padStart(2, '0')}-01`;
              const lastDay = new Date(toYear, toMonth, 0).getDate();
              const to = `${toYear}-${String(toMonth).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
              exportSnapshots(from, to, provider);
            }}
            disabled={isExporting}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
            {isExporting ? 'Exporting...' : 'Export'}
          </Button>
          {isConnected && (
            <Button
              onClick={() => capture.mutate(provider)}
              disabled={capture.isPending}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`}
              />
              {capture.isPending ? 'Capturing...' : `Capture ${providerLabel}`}
            </Button>
          )}
        </div>
      </div>

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            {isConnected
              ? `No ${providerLabel} snapshots yet. Click "Capture ${providerLabel}" to take the first one.`
              : `${providerLabel} is not configured. Set it up in ISO Settings.`}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Captured</th>
                  {columns.map((col) => (
                    <th key={col.header} className="pb-3 font-medium">{col.header}</th>
                  ))}
                  <th className="pb-3 font-medium">Review</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((snap) => (
                  <tr key={snap.id} className="border-b last:border-b-0">
                    <td className="py-3 pr-4 text-sm">
                      {formatDate(snap.captured_at)}
                    </td>
                    {columns.map((col) => (
                      <td key={col.header} className="py-3 pr-4 text-sm">
                        {col.accessor(snap)}
                      </td>
                    ))}
                    <td className="py-3 pr-4">
                      {snap.review_status ? (
                        <ReviewStatusBadge status={snap.review_status} />
                      ) : (
                        <span className="text-sm text-muted-foreground">
                          {'\u2014'}
                        </span>
                      )}
                    </td>
                    <td className="py-3">
                      <div className="flex items-center gap-1">
                        <Link to={`/iso/snapshots/${snap.id}`}>
                          <Button variant="ghost" size="sm">
                            View
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteTargetId(snap.id)}
                          aria-label="Delete snapshot"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalItems={data.total}
            shownItems={data.items.length}
            label="snapshots"
            onPageChange={onPageChange}
          />
        </>
      )}

      <AlertDialog
        open={deleteTargetId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTargetId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this snapshot?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the snapshot and its associated
              review and actions. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete}>
              {deleteSnapshot.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
