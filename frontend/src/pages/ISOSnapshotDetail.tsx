import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react';
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
  useIsoSnapshot,
  useSnapshotReview,
  useUpdateReview,
  useSignReview,
  useUnsignReview,
} from '@/hooks/useIso';
import { useUsers } from '@/hooks/useUsers';
import { formatDate } from '@/utils/formatters';
import type {
  SnapshotSummary,
  AccessReviewAction,
  AccessReviewDetail,
  DiffSummary,
  ActionDecision,
} from '@/types';

// --- Data interfaces for the snapshot detail ---

interface SnapshotUser {
  id: string;
  name: string;
  email: string;
  suspended: boolean;
  org_unit_path: string;
}

interface SnapshotGroup {
  id: string;
  name: string;
  email: string;
}

interface GroupMember {
  role: string;
  type: string;
  email: string;
}

interface RoleAssignment {
  role_id: string;
  user_id: string;
  role_name: string;
  user_email: string;
}

interface SnapshotData {
  users: SnapshotUser[];
  groups: SnapshotGroup[];
  group_members: Record<string, GroupMember[]>;
  role_assignments: RoleAssignment[];
}

type TabKey = 'users' | 'groups' | 'group_members' | 'admins';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'users', label: 'Users' },
  { key: 'groups', label: 'Groups' },
  { key: 'group_members', label: 'Group Members' },
  { key: 'admins', label: 'Admins' },
];

// --- Review helpers ---

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

function buildDiffStatItems(
  diffSummary: DiffSummary,
): { label: string; value: number }[] {
  return [
    { label: 'New Users', value: diffSummary.new_user },
    { label: 'Removed Users', value: diffSummary.removed_user },
    { label: 'Role Changes', value: diffSummary.role_change },
    { label: 'New External', value: diffSummary.new_external },
    { label: 'Group Changes', value: diffSummary.group_membership_change },
  ];
}

// --- Summary cards helper ---

function buildSummaryStatItems(
  summary: SnapshotSummary,
): { label: string; value: number }[] {
  return [
    { label: 'Total Users', value: summary.total_users },
    { label: 'Total Admins', value: summary.total_admins },
    { label: 'Total Groups', value: summary.total_groups },
    { label: 'External Members', value: summary.external_members },
  ];
}

// --- Action state for local editing ---

interface ActionState {
  actionTaken: string;
  justification: string;
  exceptionUntil: string;
}

// --- Action row component (controlled) ---

interface ActionRowProps {
  readonly action: AccessReviewAction;
  readonly state: ActionState;
  readonly isSigned: boolean;
  readonly onChange: (state: ActionState) => void;
}

function ActionRow({ action, state, isSigned, onChange }: ActionRowProps): JSX.Element {
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
            value={state.actionTaken || 'none'}
            onValueChange={(v) =>
              onChange({ ...state, actionTaken: v === 'none' ? '' : v })
            }
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
              value={state.justification}
              onChange={(e) =>
                onChange({ ...state, justification: e.target.value })
              }
              placeholder="Justification..."
              className="w-48 min-h-[60px]"
              rows={2}
            />
            {state.actionTaken === 'exception' && (
              <input
                type="date"
                value={state.exceptionUntil}
                onChange={(e) =>
                  onChange({ ...state, exceptionUntil: e.target.value })
                }
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              />
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

// --- Review panel component ---

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

function ReviewPanel({ review }: ReviewPanelProps): JSX.Element {
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

// --- Users tab ---

interface UsersTableProps {
  readonly users: SnapshotUser[];
}

function UsersTable({ users }: UsersTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Status</th>
            <th className="pb-3 font-medium">Org Unit</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{user.name}</td>
              <td className="py-3 pr-4 text-sm">{user.email}</td>
              <td className="py-3 pr-4">
                {user.suspended ? (
                  <Badge variant="destructive">Suspended</Badge>
                ) : (
                  <Badge variant="outline">Active</Badge>
                )}
              </td>
              <td className="py-3 pr-4 text-sm">{user.org_unit_path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Groups tab ---

interface GroupsTableProps {
  readonly groups: SnapshotGroup[];
  readonly groupMembers: Record<string, GroupMember[]>;
}

function GroupsTable({ groups, groupMembers }: GroupsTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Members</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr key={group.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{group.name}</td>
              <td className="py-3 pr-4 text-sm">{group.email}</td>
              <td className="py-3 pr-4 text-sm">
                {groupMembers[group.email]?.length ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Group Members tab (expandable) ---

interface GroupMembersListProps {
  readonly groupMembers: Record<string, GroupMember[]>;
}

function GroupMembersList({ groupMembers }: GroupMembersListProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupEmail: string): void => {
    setExpanded((prev) => ({ ...prev, [groupEmail]: !prev[groupEmail] }));
  };

  const groupEmails = Object.keys(groupMembers).sort();

  return (
    <div className="space-y-1">
      {groupEmails.map((groupEmail) => {
        const members = groupMembers[groupEmail];
        const isExpanded = expanded[groupEmail] ?? false;

        return (
          <div key={groupEmail}>
            <button
              type="button"
              className="flex items-center gap-2 w-full py-3 pr-4 text-sm text-left hover:bg-muted/50 rounded-md px-2"
              onClick={() => toggleGroup(groupEmail)}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              <span className="font-medium">{groupEmail}</span>
              <span className="text-muted-foreground ml-auto">
                {members.length} member{members.length !== 1 ? 's' : ''}
              </span>
            </button>
            {isExpanded && (
              <div className="ml-8 mb-2">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="pb-2 font-medium">Email</th>
                      <th className="pb-2 font-medium">Role</th>
                      <th className="pb-2 font-medium">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((member) => (
                      <tr
                        key={`${groupEmail}-${member.email}`}
                        className="border-b last:border-b-0"
                      >
                        <td className="py-2 pr-4 text-sm">{member.email}</td>
                        <td className="py-2 pr-4 text-sm">{member.role}</td>
                        <td className="py-2 pr-4">
                          {member.type !== 'USER' ? (
                            <Badge variant="secondary">External</Badge>
                          ) : (
                            <span className="text-sm">{member.type}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Admins tab ---

interface AdminsTableProps {
  readonly roleAssignments: RoleAssignment[];
}

function AdminsTable({ roleAssignments }: AdminsTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Role Name</th>
          </tr>
        </thead>
        <tbody>
          {roleAssignments.map((ra) => (
            <tr
              key={`${ra.role_id}-${ra.user_id}`}
              className="border-b last:border-b-0"
            >
              <td className="py-3 pr-4 text-sm">{ra.user_email}</td>
              <td className="py-3 pr-4 text-sm">{ra.role_name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Main page ---

export default function ISOSnapshotDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: snapshot, isLoading, error } = useIsoSnapshot(id ?? '');
  const { data: review } = useSnapshotReview(id ?? '');
  const [activeTab, setActiveTab] = useState<TabKey>('users');

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

  const snapshotData = snapshot.data as unknown as SnapshotData;
  const summary = snapshot.summary;

  const users = snapshotData.users ?? [];
  const groups = snapshotData.groups ?? [];
  const groupMembers = snapshotData.group_members ?? {};
  const roleAssignments = snapshotData.role_assignments ?? [];

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
        <div className="text-sm text-muted-foreground">
          <span>Captured {formatDate(snapshot.captured_at)}</span>
          {review?.signed_at && (
            <span className="ml-4">Signed {formatDate(review.signed_at)}</span>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <StatCards items={buildSummaryStatItems(summary)} columns={4} />

      {/* Review section */}
      {review && <ReviewPanel review={review} />}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'users' && <UsersTable users={users} />}
      {activeTab === 'groups' && (
        <GroupsTable groups={groups} groupMembers={groupMembers} />
      )}
      {activeTab === 'group_members' && (
        <GroupMembersList groupMembers={groupMembers} />
      )}
      {activeTab === 'admins' && (
        <AdminsTable roleAssignments={roleAssignments} />
      )}
    </div>
  );
}
