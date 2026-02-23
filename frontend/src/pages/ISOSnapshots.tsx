import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { ErrorBanner } from '@/components/ui/error-banner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useIsoSnapshots, useCaptureSnapshot } from '@/hooks/useIso';
import { formatDate } from '@/utils/formatters';

const snapshotsUrlSchema = {
  page: { defaultValue: 1 },
};

export default function ISOSnapshots(): JSX.Element {
  const { state, setState } = useUrlState(snapshotsUrlSchema);
  const page = state.page;

  const { data, isLoading } = useIsoSnapshots({ page, page_size: 20 });
  const capture = useCaptureSnapshot();

  const handleCapture = (): void => {
    capture.mutate();
  };

  const handlePageChange = (newPage: number): void => {
    setState({ page: newPage });
  };

  const totalPages = data?.pages ?? 0;
  const firstSnapshot = data?.items?.[0];
  const lastCaptureDate = firstSnapshot?.captured_at ?? null;

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {lastCaptureDate
            ? `Last capture: ${formatDate(lastCaptureDate)}`
            : 'No snapshots yet'}
        </p>
        <Button onClick={handleCapture} disabled={capture.isPending}>
          <RefreshCw
            className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`}
          />
          {capture.isPending ? 'Capturing...' : 'Capture Snapshot'}
        </Button>
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
                    <td className="py-3">
                      <Link to={`/iso/snapshots/${snap.id}`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
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
    </div>
  );
}
