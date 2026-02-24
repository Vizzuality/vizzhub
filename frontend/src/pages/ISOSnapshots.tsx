import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Download, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { ErrorBanner } from '@/components/ui/error-banner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ReviewStatusBadge } from '@/components/ui/review-status-badge';
import { useUrlState } from '@/shared/hooks/useUrlState';
import {
  useIsoSnapshots,
  useCaptureSnapshot,
  useDeleteSnapshot,
} from '@/hooks/useIso';
import { useIsoExport } from '@/hooks/useIsoExport';
import { isSnapshotStale } from '@/hooks/isoStaleCheck';
import { formatDate } from '@/utils/formatters';

const snapshotsUrlSchema = {
  page: { defaultValue: 1 },
};

export default function ISOSnapshots(): JSX.Element {
  const { state, setState } = useUrlState(snapshotsUrlSchema);
  const page = state.page;

  const { data, isLoading } = useIsoSnapshots({ page, page_size: 20 });
  const capture = useCaptureSnapshot();
  const deleteSnapshot = useDeleteSnapshot();
  const { exportSnapshots, isExporting } = useIsoExport();
  const currentYear = new Date().getFullYear();
  const [exportYear, setExportYear] = useState(currentYear);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const handleCapture = (): void => {
    capture.mutate();
  };

  const handlePageChange = (newPage: number): void => {
    setState({ page: newPage });
  };

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
              ? 'Last access snapshot is over 35 days old. Consider capturing a new snapshot to maintain ISO 27001 compliance.'
              : 'No access snapshots have been captured yet. Capture your first snapshot to begin ISO 27001 access reviews.'}
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
          <Select
            value={String(exportYear)}
            onValueChange={(v) => setExportYear(Number(v))}
          >
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={() =>
              exportSnapshots(`${exportYear}-01-01`, `${exportYear}-12-31`)
            }
            disabled={isExporting}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
            {isExporting ? 'Exporting...' : 'Export Year'}
          </Button>
          <Button onClick={handleCapture} disabled={capture.isPending}>
            <RefreshCw
              className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`}
            />
            {capture.isPending ? 'Capturing...' : 'Capture Snapshot'}
          </Button>
        </div>
      </div>

      {capture.isError && (
        <ErrorBanner message="Failed to capture snapshot. Please try again." />
      )}

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            No snapshots have been captured yet. Click "Capture Snapshot" to
            take the first one.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Captured</th>
                  <th className="pb-3 font-medium">Provider</th>
                  <th className="pb-3 font-medium">Users</th>
                  <th className="pb-3 font-medium">Admins</th>
                  <th className="pb-3 font-medium">Groups</th>
                  <th className="pb-3 font-medium">External</th>
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
                    <td className="py-3 pr-4">
                      <Badge variant="outline">{snap.provider}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-sm">
                      {snap.summary.total_users ?? 0}
                    </td>
                    <td className="py-3 pr-4 text-sm">
                      {snap.summary.total_admins ?? 0}
                    </td>
                    <td className="py-3 pr-4 text-sm">
                      {snap.summary.total_groups ?? 0}
                    </td>
                    <td className="py-3 pr-4 text-sm">
                      {snap.summary.external_members ?? 0}
                    </td>
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
            onPageChange={handlePageChange}
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
