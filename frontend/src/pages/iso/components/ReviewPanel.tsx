import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
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
} from '@/shared/components/ui/alert-dialog';
import { StatCards } from '@/shared/components/ui/stat-cards';
import {
  useUpdateReview,
  useSignReview,
  useUnsignReview,
} from '@/hooks/useIso';
import { useUsers } from '@/hooks/useUsers';
import type {
  AccessReviewAction,
  AccessReviewDetail,
  ActionDecision,
} from '@/types';
import ActionRow from './ActionRow';
import type { ActionState } from './ActionRow';
import { buildDiffStatItems } from './helpers';

function initActionStates(
  actions: AccessReviewAction[],
): Record<string, ActionState> {
  const states: Record<string, ActionState> = {};
  for (const action of actions) {
    states[action.id] = {
      actionTaken: action.action_taken ?? '',
      justification: action.justification ?? '',
      exceptionUntil: action.exception_until ?? '',
    };
  }
  return states;
}

interface ReviewPanelProps {
  readonly review: AccessReviewDetail;
}

export default function ReviewPanel({ review }: ReviewPanelProps): JSX.Element {
  const updateReview = useUpdateReview(review.id);
  const signReview = useSignReview(review.id);
  const unsignReview = useUnsignReview(review.id);
  const { data: users } = useUsers();

  const [notes, setNotes] = useState('');
  const [actionStates, setActionStates] = useState<Record<string, ActionState>>(
    () => initActionStates(review.actions),
  );
  const [signDialogOpen, setSignDialogOpen] = useState(false);
  const [unsignDialogOpen, setUnsignDialogOpen] = useState(false);

  useEffect(() => {
    if (review?.notes !== undefined) {
      setNotes(review.notes ?? '');
    }
  }, [review?.notes]);

  useEffect(() => {
    setActionStates(initActionStates(review.actions));
  }, [review.actions]);

  const isSigned = review.status === 'signed';

  const handleReviewerChange = useCallback(
    (value: string): void => {
      updateReview.mutate({
        reviewer_id: value === 'unassigned' ? undefined : value,
      });
    },
    [updateReview],
  );

  const handleActionChange = useCallback(
    (actionId: string, state: ActionState): void => {
      setActionStates((prev) => ({ ...prev, [actionId]: state }));
    },
    [],
  );

  const handleSign = useCallback(
    (e: React.MouseEvent): void => {
      e.preventDefault();
      const actions: ActionDecision[] = review.actions.map((action) => {
        const state = actionStates[action.id];
        return {
          action_id: action.id,
          action_taken: state.actionTaken as ActionDecision['action_taken'],
          justification: state.justification || undefined,
          exception_until:
            state.actionTaken === 'exception' && state.exceptionUntil
              ? state.exceptionUntil
              : undefined,
        };
      });
      signReview.mutate(
        { notes: notes || undefined, actions },
        {
          onSuccess: () => setSignDialogOpen(false),
          onError: () => setSignDialogOpen(false),
        },
      );
    },
    [signReview, notes, review.actions, actionStates],
  );

  const handleUnsign = useCallback(
    (e: React.MouseEvent): void => {
      e.preventDefault();
      unsignReview.mutate(undefined, {
        onSuccess: () => setUnsignDialogOpen(false),
        onError: () => setUnsignDialogOpen(false),
      });
    },
    [unsignReview],
  );

  const unresolvedCount = Object.values(actionStates).filter(
    (s) => !s.actionTaken,
  ).length;

  return (
    <div className="space-y-6" data-testid="review-panel">
      {/* Review Details card */}
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
              <Textarea
                id="review-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes about this review..."
                rows={3}
              />
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
                </tr>
              </thead>
              <tbody>
                {review.actions.map((action) => (
                  <ActionRow
                    key={action.id}
                    action={action}
                    state={actionStates[action.id] ?? {
                      actionTaken: '',
                      justification: '',
                      exceptionUntil: '',
                    }}
                    isSigned={isSigned}
                    onChange={(s) => handleActionChange(action.id, s)}
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
                      {unresolvedCount} action{unresolvedCount === 1 ? '' : 's'}{' '}
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
