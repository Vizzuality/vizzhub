import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  useIsoReview,
  useUpdateReview,
  useUpdateReviewAction,
  useSignReview,
} from '@/hooks/useIso';
import { useUsers } from '@/hooks/useUsers';
import { formatDate } from '@/utils/formatters';
import type { AccessReviewAction, AccessReviewDetail } from '@/types';

type ReviewStatus = AccessReviewDetail['status'];
type ActionTaken = NonNullable<AccessReviewAction['action_taken']>;

const ACTION_OPTIONS: { value: ActionTaken; label: string }[] = [
  { value: 'accepted', label: 'Accepted' },
  { value: 'removed', label: 'Removed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'exception', label: 'Exception' },
];

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

function formatChangeDetails(
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

interface ActionRowProps {
  readonly action: AccessReviewAction;
  readonly reviewId: string;
  readonly isSigned: boolean;
}

function ActionRow({ action, reviewId, isSigned }: ActionRowProps): JSX.Element {
  const [actionTaken, setActionTaken] = useState<string>(
    action.action_taken ?? '',
  );
  const [justification, setJustification] = useState<string>(
    action.justification ?? '',
  );
  const updateAction = useUpdateReviewAction(reviewId);

  useEffect(() => {
    setActionTaken(action.action_taken ?? '');
    setJustification(action.justification ?? '');
  }, [action.action_taken, action.justification]);

  const handleSave = (): void => {
    if (!actionTaken) return;
    updateAction.mutate({
      actionId: action.id,
      data: {
        action_taken: actionTaken as ActionTaken,
        justification: justification || undefined,
      },
    });
  };

  const hasChanges =
    actionTaken !== (action.action_taken ?? '') ||
    justification !== (action.justification ?? '');

  return (
    <tr className="border-b last:border-b-0">
      <td className="py-3 pr-4 text-sm">
        <div>
          {action.subject_label || action.subject_id}
          <span className="ml-1 text-muted-foreground">
            ({action.subject_type})
          </span>
        </div>
      </td>
      <td className="py-3 pr-4">
        <Badge variant="outline">{action.change_type}</Badge>
      </td>
      <td className="py-3 pr-4 text-sm max-w-xs truncate">
        {formatChangeDetails(action.previous_value, action.current_value)}
      </td>
      <td className="py-3 pr-4">
        {isSigned ? (
          <span className="text-sm">{action.action_taken ?? '\u2014'}</span>
        ) : (
          <Select
            value={actionTaken || 'none'}
            onValueChange={(v) => setActionTaken(v === 'none' ? '' : v)}
            disabled={isSigned}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Select...</SelectItem>
              {ACTION_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </td>
      <td className="py-3 pr-4">
        {isSigned ? (
          <span className="text-sm">{action.justification ?? '\u2014'}</span>
        ) : (
          <Input
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            placeholder="Justification..."
            className="w-40"
            disabled={isSigned}
          />
        )}
      </td>
      <td className="py-3">
        {!isSigned && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleSave}
            disabled={!actionTaken || !hasChanges || updateAction.isPending}
          >
            {updateAction.isPending ? 'Saving...' : 'Save'}
          </Button>
        )}
      </td>
    </tr>
  );
}

interface DiffSummaryCardsProps {
  readonly diffSummary: Record<string, unknown>;
}

function DiffSummaryCards({ diffSummary }: DiffSummaryCardsProps): JSX.Element {
  const stats = diffSummary as Record<string, number>;
  const items: { label: string; key: string }[] = [
    { label: 'New Users', key: 'new_users' },
    { label: 'Removed Users', key: 'removed_users' },
    { label: 'Role Changes', key: 'role_changes' },
    { label: 'New External', key: 'new_external' },
    { label: 'Group Changes', key: 'group_changes' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {items.map(({ label, key }) => (
        <Card key={key}>
          <CardContent className="pt-4 pb-4 text-center">
            <p className="text-2xl font-semibold">{stats[key] ?? 0}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function ISOReviewDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: review, isLoading, error } = useIsoReview(id ?? '');
  const updateReview = useUpdateReview(id ?? '');
  const signReview = useSignReview(id ?? '');
  const { data: users } = useUsers();

  const [notes, setNotes] = useState('');
  const [signDialogOpen, setSignDialogOpen] = useState(false);

  useEffect(() => {
    if (review?.notes !== undefined) {
      setNotes(review.notes ?? '');
    }
  }, [review?.notes]);

  const isSigned = review?.status === 'signed';

  const handleReviewerChange = useCallback(
    (value: string): void => {
      updateReview.mutate({
        reviewer_id: value === 'unassigned' ? undefined : value,
      });
    },
    [updateReview],
  );

  const handleSaveNotes = useCallback((): void => {
    updateReview.mutate({ notes });
  }, [updateReview, notes]);

  const handleSign = useCallback(
    (e: React.MouseEvent): void => {
      e.preventDefault();
      signReview.mutate(undefined, {
        onSuccess: () => {
          setSignDialogOpen(false);
        },
        onError: () => {
          setSignDialogOpen(false);
        },
      });
    },
    [signReview],
  );

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error || !review) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          onClick={() => navigate('/iso/reviews')}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Reviews
        </Button>
        <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load review.
        </div>
      </div>
    );
  }

  const unresolvedCount = review.actions.filter(
    (a) => a.action_taken === null,
  ).length;

  const notesChanged = notes !== (review.notes ?? '');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate('/iso/reviews')}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Reviews
          </Button>
          <h2 className="text-2xl font-semibold">Access Review</h2>
          {getStatusBadge(review.status)}
        </div>
        <div className="text-sm text-muted-foreground">
          <span>Created {formatDate(review.created_at)}</span>
          {review.signed_at && (
            <span className="ml-4">Signed {formatDate(review.signed_at)}</span>
          )}
        </div>
      </div>

      {/* Review info card */}
      <Card>
        <CardHeader>
          <CardTitle>Review Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm text-muted-foreground">Scope</Label>
            <p className="text-sm mt-1">{review.scope}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="reviewer-select">Reviewer</Label>
            <Select
              value={review.reviewer_id ?? 'unassigned'}
              onValueChange={handleReviewerChange}
              disabled={isSigned}
            >
              <SelectTrigger id="reviewer-select" className="w-72">
                <SelectValue placeholder="Select reviewer..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="unassigned">Unassigned</SelectItem>
                {users?.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="review-notes">Notes</Label>
            <Textarea
              id="review-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes about this review..."
              disabled={isSigned}
              rows={3}
            />
            {!isSigned && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleSaveNotes}
                disabled={!notesChanged || updateReview.isPending}
              >
                {updateReview.isPending ? 'Saving...' : 'Save Notes'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Diff Summary */}
      {review.diff_summary && (
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Diff Summary</h3>
          <DiffSummaryCards diffSummary={review.diff_summary} />
        </div>
      )}

      {/* Actions table */}
      {review.actions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Actions</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Subject</th>
                  <th className="pb-3 font-medium">Change Type</th>
                  <th className="pb-3 font-medium">Details</th>
                  <th className="pb-3 font-medium">Action</th>
                  <th className="pb-3 font-medium">Justification</th>
                  {!isSigned && <th className="pb-3 font-medium" />}
                </tr>
              </thead>
              <tbody>
                {review.actions.map((action) => (
                  <ActionRow
                    key={action.id}
                    action={action}
                    reviewId={review.id}
                    isSigned={isSigned}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sign section */}
      {!isSigned && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                {unresolvedCount > 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {unresolvedCount} action{unresolvedCount !== 1 ? 's' : ''}{' '}
                    still unresolved. All actions must be resolved before
                    signing.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    All actions resolved. Ready to sign.
                  </p>
                )}
              </div>
              <AlertDialog
                open={signDialogOpen}
                onOpenChange={setSignDialogOpen}
              >
                <AlertDialogTrigger asChild>
                  <Button disabled={unresolvedCount > 0}>Sign Review</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Sign this review?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Signing this review will lock all actions and mark the
                      review as complete. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleSign}>
                      {signReview.isPending ? 'Signing...' : 'Sign'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
