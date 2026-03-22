/**
 * User detail / edit page (admin only)
 */

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import {
  useUser,
  useUpdateUser,
  useDeleteUser,
  useFunctionalAreas,
  useRates,
  useSyncSlack,
  useAvailableRoles,
  useAssignRoles,
} from '@/core/hooks/useUsers';
import { useAuth } from '@/core/hooks/useAuth';
import { getFullName } from '@/utils/formatters';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
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
} from '@/shared/components/ui/alert-dialog';

const NONE_VALUE = '__none__';

function DedicationInput({
  value,
  onSave,
}: {
  readonly value: number | null;
  readonly onSave: (val: number | null) => void;
}): JSX.Element {
  const [local, setLocal] = useState(value?.toString() ?? '');

  return (
    <div className="space-y-1.5">
      <Label>Dedication</Label>
      <Input
        type="number"
        min={0}
        max={1}
        step={0.05}
        value={local}
        placeholder="e.g. 1.00"
        className="w-[200px]"
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          const parsed = local ? Number.parseFloat(local) : null;
          if (parsed !== value) onSave(parsed);
        }}
      />
    </div>
  );
}

export default function UserDetail(): JSX.Element {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const { data: user, isLoading, error } = useUser(userId!);
  const { data: functionalAreas } = useFunctionalAreas();
  const { data: rates } = useRates();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();
  const syncSlack = useSyncSlack();
  const { data: availableRoles } = useAvailableRoles();
  const assignRoles = useAssignRoles();

  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showDeactivateDialog, setShowDeactivateDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const isCurrentUser = currentUser?.id === userId;

  const showMessage = (type: 'success' | 'error', text: string): void => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleFieldChange = async (field: string, value: unknown): Promise<void> => {
    if (!userId) return;
    try {
      await updateUser.mutateAsync({ userId, data: { [field]: value } });
      showMessage('success', 'User updated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update');
    }
  };

  const handleToggleActive = async (active: boolean): Promise<void> => {
    if (!userId) return;
    try {
      await updateUser.mutateAsync({ userId, data: { active } });
      showMessage('success', active ? 'User activated' : 'User deactivated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update status');
    } finally {
      setShowDeactivateDialog(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!userId) return;
    try {
      await deleteUser.mutateAsync(userId);
      navigate('/admin/users');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to delete');
      setShowDeleteDialog(false);
    }
  };

  if (isLoading) return <LoadingSpinner className="py-8" />;

  if (error || !user) {
    return (
      <div className="text-destructive text-center py-8">
        {error ? `Error: ${error.message}` : 'User not found'}
      </div>
    );
  }

  const fullName = getFullName(user.first_name, user.last_name, user.email);

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/admin/users">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-lg font-semibold">{fullName}</h2>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
            user.active ? 'bg-green-500' : 'bg-muted-foreground'
          }`} />
          <span className="text-sm text-foreground">
            {user.active ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-md text-sm ${
          message.type === 'success' ? 'bg-green-500/10 text-green-500' : 'bg-destructive/10 text-destructive'
        }`}>
          {message.text}
        </div>
      )}

      <div className="border rounded-lg p-6 space-y-5">
        {/* Email (read-only) */}
        <div className="space-y-1.5">
          <Label className="text-muted-foreground">Email</Label>
          <Input value={user.email} disabled className="bg-muted" />
        </div>

        {/* Name (read-only, set from Google) */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-muted-foreground">First name</Label>
            <Input value={user.first_name ?? ''} disabled className="bg-muted" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-muted-foreground">Last name</Label>
            <Input value={user.last_name ?? ''} disabled className="bg-muted" />
          </div>
        </div>

        {/* Roles */}
        <div className="space-y-1.5">
          <Label>Roles</Label>
          <div className="flex flex-col gap-2">
            {availableRoles?.map((role) => (
              <label key={role.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={user.roles.includes(role.name)}
                  disabled={role.name === 'user' || isCurrentUser || assignRoles.isPending}
                  onChange={async (e) => {
                    const newRoles = e.target.checked
                      ? [...user.roles, role.name]
                      : user.roles.filter((r) => r !== role.name);
                    try {
                      await assignRoles.mutateAsync({
                        userId: userId!,
                        roles: newRoles,
                      });
                      showMessage('success', 'Roles updated');
                    } catch (err) {
                      showMessage(
                        'error',
                        err instanceof Error ? err.message : 'Failed to assign roles',
                      );
                    }
                  }}
                  className="rounded border-input"
                />
                <span className="capitalize">{role.name}</span>
                {role.description && (
                  <span className="text-muted-foreground text-xs">
                    — {role.description}
                  </span>
                )}
              </label>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Role changes take effect on the user&apos;s next login.
          </p>
        </div>

        {/* Functional Area */}
        <div className="space-y-1.5">
          <Label>Functional area</Label>
          <Select
            value={user.functional_area_id ?? NONE_VALUE}
            onValueChange={(value) =>
              handleFieldChange('functional_area_id', value === NONE_VALUE ? null : value)
            }
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Not set" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>Not set</SelectItem>
              {functionalAreas?.map((fa) => (
                <SelectItem key={fa.id} value={fa.id}>{fa.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Rate */}
        <div className="space-y-1.5">
          <Label>Rate band</Label>
          <Select
            value={user.rate_id ?? NONE_VALUE}
            onValueChange={(value) =>
              handleFieldChange('rate_id', value === NONE_VALUE ? null : value)
            }
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Not set" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>Not set</SelectItem>
              {rates?.map((r) => (
                <SelectItem key={r.id} value={r.id}>{r.code}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Dedication */}
        <DedicationInput
          value={user.dedication}
          onSave={(val) => handleFieldChange('dedication', val)}
        />
      </div>

      {/* Slack */}
      <div className="border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Slack</h3>
        <div className="flex items-center justify-between">
          {user.slack_display_name ? (
            <div className="space-y-1">
              <p className="text-sm">{user.slack_display_name}</p>
              <p className="text-xs text-muted-foreground">{user.slack_user_id}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Not linked</p>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (!userId) return;
              const label = user.slack_display_name ? 'updated' : 'linked';
              syncSlack.mutateAsync(userId)
                .then(() => showMessage('success', `Slack profile ${label}`))
                .catch((err) => showMessage('error', err?.response?.data?.detail ?? 'Sync failed'));
            }}
            disabled={syncSlack.isPending}
          >
            {syncSlack.isPending ? 'Syncing...' : user.slack_display_name ? 'Re-sync' : 'Link Slack'}
          </Button>
        </div>
      </div>

      {/* Actions */}
      <div className="border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Actions</h3>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">
              {user.active ? 'Deactivate user' : 'Activate user'}
            </p>
            <p className="text-sm text-muted-foreground">
              {user.active
                ? 'Deactivated users cannot log in or be impersonated.'
                : 'Reactivate this user to restore access.'}
            </p>
          </div>
          {user.active ? (
            <Button
              variant="outline"
              onClick={() => setShowDeactivateDialog(true)}
              disabled={isCurrentUser}
            >
              Deactivate
            </Button>
          ) : (
            <Button variant="outline" onClick={() => handleToggleActive(true)}>
              Activate
            </Button>
          )}
        </div>

        <div className="border-t pt-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-destructive">Delete user</p>
            <p className="text-sm text-muted-foreground">
              Permanently remove this user. This cannot be undone.
            </p>
          </div>
          <Button
            variant="destructive"
            onClick={() => setShowDeleteDialog(true)}
            disabled={isCurrentUser}
          >
            Delete
          </Button>
        </div>
      </div>

      {/* Deactivate confirmation */}
      <AlertDialog open={showDeactivateDialog} onOpenChange={setShowDeactivateDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate user</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {user.email}?
              They will no longer be able to log in.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); handleToggleActive(false); }}
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete confirmation */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to permanently delete {user.email}?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); handleDelete(); }}
              className="bg-destructive text-destructive-foreground"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
