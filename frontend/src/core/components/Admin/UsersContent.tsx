/**
 * User management tab in Admin panel
 */

import { useState } from 'react';
import { useUsers, useUpdateUserRole, useDeleteUser, useToggleUserActive } from '../../hooks/useUsers';
import { useAuth } from '../../hooks/useAuth';
import { User, UserRole } from '../../types/auth';
import { getFullName } from '@/utils/formatters';
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
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import { Trash2 } from 'lucide-react';

function formatDate(dateString: string | null): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

export function UsersContent(): JSX.Element {
  const [showInactive, setShowInactive] = useState(false);
  const { data: users, isLoading, error } = useUsers(showInactive);
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();
  const toggleActive = useToggleUserActive();
  const { user: currentUser } = useAuth();

  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const showMessage = (type: 'success' | 'error', text: string): void => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleRoleChange = async (userId: string, newRole: UserRole): Promise<void> => {
    try {
      await updateRole.mutateAsync({ userId, role: newRole });
      showMessage('success', 'User role updated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update role');
    }
  };

  const handleToggleActive = async (userId: string, active: boolean): Promise<void> => {
    try {
      await toggleActive.mutateAsync({ userId, active });
      showMessage('success', active ? 'User activated' : 'User deactivated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update status');
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!userToDelete) return;

    try {
      await deleteUser.mutateAsync(userToDelete.id);
      showMessage('success', 'User deleted');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setUserToDelete(null);
    }
  };

  if (isLoading) {
    return <LoadingSpinner className="py-8" />;
  }

  if (error) {
    return (
      <div className="text-destructive text-center py-8">
        Error loading users: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Users</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="show-inactive"
              checked={showInactive}
              onCheckedChange={setShowInactive}
            />
            <Label htmlFor="show-inactive" className="text-sm text-muted-foreground">
              Show inactive
            </Label>
          </div>
          <span className="text-muted-foreground text-sm">
            {users?.length || 0} users
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

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Email</th>
              <th className="text-left p-3 font-medium">Name</th>
              <th className="text-left p-3 font-medium">Role</th>
              <th className="text-left p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium">Last Login</th>
              <th className="w-[80px] p-3"></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((user) => {
              const isCurrentUser = currentUser?.id === user.id;
              const fullName = getFullName(user.first_name, user.last_name, '-');

              return (
                <tr key={user.id} className={`border-t ${!user.active ? 'opacity-60' : ''}`}>
                  <td className="p-3 font-medium">{user.email}</td>
                  <td className="p-3">{fullName}</td>
                  <td className="p-3">
                    <Select
                      value={user.role}
                      onValueChange={(value) => handleRoleChange(user.id, value as UserRole)}
                      disabled={isCurrentUser}
                    >
                      <SelectTrigger className="w-[100px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">user</SelectItem>
                        <SelectItem value="admin">admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        user.active ? 'bg-green-500' : 'bg-muted-foreground'
                      }`} />
                      <span className="text-sm text-foreground">
                        {user.active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </td>
                  <td className="p-3 text-muted-foreground text-sm">
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="p-3 flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleActive(user.id, !user.active)}
                      disabled={isCurrentUser}
                      title={isCurrentUser ? 'Cannot change your own status' : user.active ? 'Deactivate user' : 'Activate user'}
                    >
                      {user.active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setUserToDelete(user)}
                      disabled={isCurrentUser}
                      title={isCurrentUser ? 'Cannot delete yourself' : 'Delete user'}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <AlertDialog open={!!userToDelete} onOpenChange={() => setUserToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {userToDelete?.email}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
