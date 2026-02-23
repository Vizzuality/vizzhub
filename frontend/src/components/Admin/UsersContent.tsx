/**
 * User management tab in Admin panel
 */

import { useState } from 'react';
import { useUsers, useUpdateUserRole, useDeleteUser } from '../../hooks/useUsers';
import { useAuth } from '../../hooks/useAuth';
import { User, UserRole } from '../../types/auth';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { LoadingSpinner } from '../ui/loading-spinner';
import { Trash2 } from 'lucide-react';

function formatDate(dateString: string | null): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

export function UsersContent(): JSX.Element {
  const { data: users, isLoading, error } = useUsers();
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();
  const { user: currentUser } = useAuth();

  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleRoleChange = async (userId: string, newRole: UserRole): Promise<void> => {
    try {
      await updateRole.mutateAsync({ userId, role: newRole });
      setMessage({ type: 'success', text: 'User role updated' });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update role' });
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!userToDelete) return;

    try {
      await deleteUser.mutateAsync(userToDelete.id);
      setMessage({ type: 'success', text: 'User deleted' });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to delete user' });
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
        <span className="text-muted-foreground text-sm">
          {users?.length || 0} users
        </span>
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
              <th className="text-left p-3 font-medium">Last Login</th>
              <th className="w-[80px] p-3"></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((user) => {
              const isCurrentUser = currentUser?.id === user.id;
              const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ') || '-';

              return (
                <tr key={user.id} className="border-t">
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
                  <td className="p-3 text-muted-foreground text-sm">
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="p-3">
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
