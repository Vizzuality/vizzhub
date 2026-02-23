import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ReviewStatusBadge } from '@/components/ui/review-status-badge';
import { PaginationControls } from '@/components/ui/pagination-controls';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useIsoReviews } from '@/hooks/useIso';
import { formatDate } from '@/utils/formatters';

const reviewsUrlSchema = {
  page: { defaultValue: 1 },
  status: { defaultValue: 'all' },
};

export default function ISOReviews(): JSX.Element {
  const { state, setState } = useUrlState(reviewsUrlSchema);
  const page = state.page;
  const statusFilter = state.status;

  const params = useMemo(() => ({
    page,
    page_size: 20,
    ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
  }), [page, statusFilter]);

  const { data, isLoading } = useIsoReviews(params);

  const handleStatusChange = (value: string): void => {
    setState({ status: value, page: 1 });
  };

  const handlePageChange = (newPage: number): void => {
    setState({ page: newPage });
  };

  const totalPages = data?.pages ?? 0;

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="w-48">
          <Select value={statusFilter} onValueChange={handleStatusChange}>
            <SelectTrigger>
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="signed">Signed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            No reviews found. Reviews are created automatically when a new
            snapshot is captured.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Scope</th>
                  <th className="pb-3 font-medium">Changes</th>
                  <th className="pb-3 font-medium">Signed</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((review) => {
                  const totalChanges = review.diff_summary?.total_changes ?? 0;
                  return (
                    <tr key={review.id} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 text-sm">
                        {formatDate(review.created_at)}
                      </td>
                      <td className="py-3 pr-4">
                        <ReviewStatusBadge status={review.status} />
                      </td>
                      <td className="py-3 pr-4 text-sm">{review.scope}</td>
                      <td className="py-3 pr-4 text-sm">{totalChanges}</td>
                      <td className="py-3 pr-4 text-sm">
                        {review.signed_at
                          ? formatDate(review.signed_at)
                          : '\u2014'}
                      </td>
                      <td className="py-3">
                        <Link to={`/iso/reviews/${review.id}`}>
                          <Button variant="ghost" size="sm">
                            View
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalItems={data.total}
            shownItems={data.items.length}
            label="reviews"
            onPageChange={handlePageChange}
          />
        </>
      )}
    </div>
  );
}
