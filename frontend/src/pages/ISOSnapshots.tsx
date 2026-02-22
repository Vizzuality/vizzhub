import { useState } from 'react';
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { useIsoSnapshots, useCaptureSnapshot } from '@/hooks/useIso';
import { formatDate } from '@/utils/formatters';

export default function ISOSnapshots(): JSX.Element {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useIsoSnapshots({ page, page_size: 20 });
  const capture = useCaptureSnapshot();

  const handleCapture = (): void => {
    capture.mutate();
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
        <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to capture snapshot. Please try again.
        </div>
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
                </tr>
              </thead>
              <tbody>
                {data.items.map((snap) => {
                  const summary = snap.summary as Record<string, number>;
                  return (
                    <tr key={snap.id} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 text-sm">
                        {formatDate(snap.captured_at)}
                      </td>
                      <td className="py-3 pr-4">
                        <Badge variant="outline">{snap.provider}</Badge>
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {summary.total_users ?? 0}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {summary.total_admins ?? 0}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {summary.total_groups ?? 0}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {summary.external_members ?? 0}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between pt-4">
            <p className="text-sm text-muted-foreground">
              Showing {data.items.length} of {data.total} snapshots
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p - 1)}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
