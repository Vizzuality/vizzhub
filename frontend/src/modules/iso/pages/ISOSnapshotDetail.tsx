import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { ReviewStatusBadge } from '@/modules/iso/components/review-status-badge';
import { ErrorBanner } from '@/shared/components/ui/error-banner';
import { StatCards } from '@/modules/iso/components/stat-cards';
import { useIsoSnapshot, useSnapshotReview } from '@/modules/iso/hooks/useIso';
import { useIsoExport } from '@/modules/iso/hooks/useIsoExport';
import { formatDate } from '@/utils/formatters';
import ReviewPanel from '../components/ReviewPanel';
import SnapshotDataTabs from '../components/SnapshotDataTabs';
import type { SnapshotData } from '../components/SnapshotDataTabs';
import GitHubDataTabs from '../components/GitHubDataTabs';
import type { GitHubSnapshotData } from '../components/GitHubDataTabs';
import { buildSummaryStatItems } from '../components/helpers';

export default function ISOSnapshotDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: snapshot, isLoading, error } = useIsoSnapshot(id ?? '');
  const { data: review } = useSnapshotReview(id ?? '');
  const { exportSnapshot, isExporting: isExportingSnapshot } = useIsoExport();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error || !snapshot) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          onClick={() => navigate('/iso/snapshots')}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Snapshots
        </Button>
        <ErrorBanner message="Failed to load snapshot." />
      </div>
    );
  }

  const isGitHub = snapshot.provider === 'github';
  const summary = snapshot.summary;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate('/iso/snapshots')}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Snapshots
          </Button>
          <h2 className="text-2xl font-semibold">Snapshot Detail</h2>
          <Badge variant="outline">{snapshot.provider}</Badge>
          {review && <ReviewStatusBadge status={review.status} />}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-muted-foreground">
            <span>Captured {formatDate(snapshot.captured_at)}</span>
            {review?.signed_at && (
              <span className="ml-4">Signed {formatDate(review.signed_at)}</span>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => exportSnapshot(id!, snapshot.captured_at)}
            disabled={isExportingSnapshot}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
            {isExportingSnapshot ? 'Exporting...' : 'Export'}
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <StatCards
        items={buildSummaryStatItems(summary, snapshot.provider)}
        columns={4}
      />

      {/* Review section */}
      {review && <ReviewPanel review={review} />}

      {/* Data tabs */}
      {isGitHub ? (
        <GitHubDataTabs data={snapshot.data as unknown as GitHubSnapshotData} />
      ) : (
        <SnapshotDataTabs data={snapshot.data as unknown as SnapshotData} />
      )}
    </div>
  );
}
