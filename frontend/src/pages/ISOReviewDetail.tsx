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
import { ReviewStatusBadge } from '@/components/ui/review-status-badge';
import { ErrorBanner } from '@/components/ui/error-banner';
import { StatCards } from '@/components/ui/stat-cards';
import {
  useIsoReview,
  useUpdateReview,
  useUpdateReviewAction,
  useSignReview,
  useUnsignReview,
} from '@/hooks/useIso';
import { useUsers } from '@/hooks/useUsers';
import { formatDate } from '@/utils/formatters';
import type { AccessReviewAction, DiffSummary } from '@/types';

type ActionTaken = NonNullable<AccessReviewAction['action_taken']>;

const ACTION_OPTIONS: { value: ActionTaken; label: string }[] = [
  { value: 'accepted', label: 'Accepted' },
  { value: 'removed', label: 'Removed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'exception', label: 'Exception' },
];

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

function getChangeTypeBadgeClasses(changeType: string): string {
  switch (changeType) {
    case 'new_user':
    case 'new_external':
      return 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800';
    case 'removed_user':
      return 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800';
    case 'role_change':
    case 'group_membership_change':
      return 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800';
    default:
      return '';
  }
}

function formatChangeType(changeType: string): string {
  return changeType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
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
  const [exceptionUntil, setExceptionUntil] = useState<string>(
    action.exception_until ?? '',
  );
  const updateAction = useUpdateReviewAction(reviewId);

  useEffect(() => {
    setActionTaken(action.action_taken ?? '');
    setJustification(action.justification ?? '');
    setExceptionUntil(action.exception_until ?? '');
  }, [action.action_taken, action.justification, action.exception_until]);

  const handleSave = (): void => {
    if (!actionTaken) return;
    updateAction.mutate({
      actionId: action.id,
      data: {
        action_taken: actionTaken as ActionTaken,
        justification: justification || undefined,
        exception_until: actionTaken === 'exception' && exceptionUntil
          ? exceptionUntil
          : undefined,
      },
    });
  };

  const hasChanges =
    actionTaken !== (action.action_taken ?? '') ||
    justification !== (action.justification ?? '') ||
    exceptionUntil !== (action.exception_until ?? '');

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
        <Badge variant="outline" className={getChangeTypeBadgeClasses(action.change_type)}>
          {formatChangeType(action.change_type)}
        </Badge>
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
          <div className="space-y-2">
            <Textarea
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="Justification..."
              className="w-48 min-h-[60px]"
              rows={2}
              disabled={isSigned}
            />
            {actionTaken === 'exception' && (
              <input
                type="date"
                value={exceptionUntil}
                onChange={(e) => setExceptionUntil(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                disabled={isSigned}
              />
            )}
          </div>
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

function buildDiffStatItems(diffSummary: DiffSummary): { label: string; value: number }[] {
  return [
    { label: 'New Users', value: diffSummary.new_user },
    { label: 'Removed Users', value: diffSummary.removed_user },
    { label: 'Role Changes', value: diffSummary.role_change },
    { label: 'New External', value: diffSummary.new_external },
    { label: 'Group Changes', value: diffSummary.group_membership_change },
  ];
}

export default function ISOReviewDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: review, isLoading, error } = useIsoReview(id ?? '');
  const updateReview = useUpdateReview(id ?? '');
  const signReview = useSignReview(id ?? '');
  const unsignReview = useUnsignReview(id ?? '');
  const { data: users } = useUsers();

  const [notes, setNotes] = useState('');
  const [signDialogOpen, setSignDialogOpen] = useState(false);
  const [unsignDialogOpen, setUnsignDialogOpen] = useState(false);

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

  const handleUnsign = useCallback(
    (e: React.MouseEvent): void => {
      e.preventDefault();
      unsignReview.mutate(undefined, {
        onSuccess: () => {
          setUnsignDialogOpen(false);
        },
        onError: () => {
          setUnsignDialogOpen(false);
        },
      });
    },
    [unsignReview],
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
        <ErrorBanner message="Failed to load review." />
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
          <ReviewStatusBadge status={review.status} />
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
            {isSigned ? (
              <p className="text-sm mt-1">
                {review.notes || '\u2014'}
              </p>
            ) : (
              <>
                <Textarea
                  id="review-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add notes about this review..."
                  rows={3}
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveNotes}
                  disabled={!notesChanged || updateReview.isPending}
                >
                  {updateReview.isPending ? 'Saving...' : 'Save Notes'}
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Diff Summary */}
      {review.diff_summary && (
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Diff Summary</h3>
          <StatCards
            items={buildDiffStatItems(review.diff_summary)}
            columns={5}
          />
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

      {/* Sign / Unsign section */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            {isSigned ? (
              <>
                <p className="text-sm text-muted-foreground">
                  This review is signed and locked.
                </p>
                <AlertDialog
                  open={unsignDialogOpen}
                  onOpenChange={setUnsignDialogOpen}
                >
                  <AlertDialogTrigger asChild>
                    <Button variant="outline">Unsign Review</Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Unsign this review?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will reopen the review for editing. All action
                        decisions will be preserved but the review will no
                        longer be considered signed.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleUnsign}>
                        {unsignReview.isPending ? 'Unsigning...' : 'Unsign'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </>
            ) : (
              <>
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
                        review as complete.
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
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
