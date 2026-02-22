import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useIsoReviews } from '@/hooks/useIso';
import { formatDate } from '@/utils/formatters';
import type { AccessReview } from '@/types';

type ReviewStatus = AccessReview['status'];

function getStatusBadge(status: ReviewStatus): JSX.Element {
  const config: Record<
    ReviewStatus,
    { variant: 'default' | 'secondary' | 'outline'; label: string }
  > = {
    draft: { variant: 'secondary', label: 'Draft' },
    completed: { variant: 'outline', label: 'Completed' },
    signed: { variant: 'default', label: 'Signed' },
  };
  const { variant, label } = config[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export default function ISOReviews(): JSX.Element {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('all');

  const params = {
    page,
    page_size: 20,
    ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
  };

  const { data, isLoading } = useIsoReviews(params);

  const handleStatusChange = (value: string): void => {
    setStatusFilter(value);
    setPage(1);
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
                  const diffSummary = review.diff_summary as Record<
                    string,
                    number
                  > | null;
                  const totalChanges = diffSummary?.total_changes ?? 0;
                  return (
                    <tr key={review.id} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 text-sm">
                        {formatDate(review.created_at)}
                      </td>
                      <td className="py-3 pr-4">
                        {getStatusBadge(review.status)}
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

          <div className="flex items-center justify-between pt-4">
            <p className="text-sm text-muted-foreground">
              Showing {data.items.length} of {data.total} reviews
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
