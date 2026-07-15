/**
 * User management tab in Admin panel
 */

import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Search, ArrowUp, ArrowDown, ArrowUpDown, ChevronRight } from 'lucide-react';
import { useUsers, useUpdateUser, useSyncSlackAll, useFunctionalAreas, useRates } from '../../hooks/useUsers';
import { useAuth } from '../../hooks/useAuth';
import { User } from '../../types/auth';
import { getFullName } from '@/utils/formatters';
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
import { Input } from '@/shared/components/ui/input';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { cn } from '@/lib/utils';
import { useUrlState } from '@/shared/hooks/useUrlState';

const SEARCH_DEBOUNCE_MS = 300;
type SortField = 'email' | 'name';
type SortOrder = 'asc' | 'desc';

function formatDate(dateString: string | null): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

function SortButton({
  field,
  label,
  currentField,
  currentOrder,
  onClick,
}: {
  readonly field: SortField;
  readonly label: string;
  readonly currentField: string;
  readonly currentOrder: string;
  readonly onClick: (field: SortField) => void;
}): JSX.Element {
  const isActive = currentField === field;
  const activeIcon = currentOrder === 'asc' ? ArrowUp : ArrowDown;
  const Icon = isActive ? activeIcon : ArrowUpDown;
  return (
    <button
      onClick={() => onClick(field)}
      className={cn(
        'flex items-center gap-1 px-2 py-1 text-sm font-medium rounded-md transition-colors',
        isActive
          ? 'bg-muted text-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
      )}
    >
      {label}
      <Icon className="w-3.5 h-3.5" />
    </button>
  );
}

function sortUsers(users: User[], field: SortField, order: SortOrder): User[] {
  return [...users].sort((a, b) => {
    let cmp: number;
    if (field === 'email') {
      cmp = a.email.localeCompare(b.email);
    } else {
      const nameA = getFullName(a.first_name, a.last_name, a.email);
      const nameB = getFullName(b.first_name, b.last_name, b.email);
      cmp = nameA.localeCompare(nameB);
    }
    return order === 'asc' ? cmp : -cmp;
  });
}

export function UsersContent(): JSX.Element {
  const { state, setState } = useUrlState({
    search: { defaultValue: '' },
    sort_by: { defaultValue: 'name' },
    sort_order: { defaultValue: 'asc' },
    area: { defaultValue: '' },
  });

  const [showInactive, setShowInactive] = useState(false);
  const { data: users, isLoading, error } = useUsers(showInactive);
  const { data: functionalAreas } = useFunctionalAreas();
  const { data: rates } = useRates();
  const updateUser = useUpdateUser();
  const syncSlackAll = useSyncSlackAll();
  const { user: currentUser } = useAuth();

  const [localSearch, setLocalSearch] = useState(state.search);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [userToDeactivate, setUserToDeactivate] = useState<User | null>(null);

  useEffect(() => { setLocalSearch(state.search); }, [state.search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== state.search) {
        setState({ search: localSearch });
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, state.search, setState]);

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    const q = state.search.toLowerCase();
    let filtered = q
      ? users.filter((u) =>
          u.email.toLowerCase().includes(q)
          || getFullName(u.first_name, u.last_name).toLowerCase().includes(q),
        )
      : users;
    if (state.area) {
      filtered = filtered.filter((u) => u.functional_area_id === state.area);
    }
    return sortUsers(filtered, state.sort_by as SortField, state.sort_order as SortOrder);
  }, [users, state.search, state.sort_by, state.sort_order, state.area]);

  const showMessage = (type: 'success' | 'error', text: string): void => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleToggleActive = async (userId: string, active: boolean): Promise<void> => {
    try {
      await updateUser.mutateAsync({ userId, data: { active } });
      showMessage('success', active ? 'User activated' : 'User deactivated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update status');
    }
  };

  const handleSort = (field: SortField): void => {
    if (state.sort_by === field) {
      setState({ sort_order: state.sort_order === 'asc' ? 'desc' : 'asc' });
    } else {
      setState({ sort_by: field, sort_order: 'asc' });
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
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search by name or email..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            className="pl-9 h-8"
          />
        </div>

        <Select
          value={state.area || 'all'}
          onValueChange={(v) => setState({ area: v === 'all' ? '' : v })}
        >
          <SelectTrigger className="h-8 w-[180px]">
            <SelectValue placeholder="All areas" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All areas</SelectItem>
            {functionalAreas?.map((fa) => (
              <SelectItem key={fa.id} value={fa.id}>{fa.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1 ml-auto">
          <SortButton field="name" label="Name" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
          <SortButton field="email" label="Email" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
        </div>

        <span className="text-muted-foreground text-sm">
          {filteredUsers.length} users
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            syncSlackAll.mutateAsync()
              .then((updated) => showMessage('success', `Synced Slack for ${updated.length} users`))
              .catch((err) => showMessage('error', err?.response?.data?.detail ?? 'Sync failed'));
          }}
          disabled={syncSlackAll.isPending}
        >
          {syncSlackAll.isPending ? 'Syncing...' : 'Sync Slack'}
        </Button>

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
      </div>

      {message && (
        <div className={`p-3 rounded-md text-sm ${
          message.type === 'success' ? 'bg-green-500/10 text-green-500' : 'bg-destructive/10 text-destructive'
        }`}>
          {message.text}
        </div>
      )}

      {/* Table */}
      <div className="border rounded-lg overflow-hidden bg-card">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Name</th>
              <th className="text-left p-3 font-medium">Email / Slack</th>
              <th className="text-left p-3 font-medium">Roles</th>
              <th className="text-left p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium hidden md:table-cell">Dedication</th>
              <th className="text-left p-3 font-medium hidden md:table-cell">Rate</th>
              <th className="text-left p-3 font-medium hidden sm:table-cell">Last Login</th>
              <th className="w-[80px] p-3"></th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((user) => {
              const isCurrentUser = currentUser?.id === user.id;
              const fullName = getFullName(user.first_name, user.last_name, user.email);
              let statusTitle: string;
              if (isCurrentUser) statusTitle = 'Cannot change your own status';
              else if (user.active) statusTitle = 'Click to deactivate';
              else statusTitle = 'Click to activate';

              return (
                <tr key={user.id} className={`border-t ${!user.active ? 'opacity-60' : ''}`}>
                  <td className="p-3">
                    <Link
                      to={`/admin/users/${user.id}`}
                      className="font-medium hover:underline"
                    >
                      {fullName}
                    </Link>
                  </td>
                  <td className="p-3 max-w-[180px]">
                    <p className="text-sm text-muted-foreground truncate" title={user.email}>{user.email}</p>
                    {user.slack_display_name && (
                      <p className="text-xs text-muted-foreground/70 truncate">{user.slack_display_name}</p>
                    )}
                  </td>
                  <td className="p-3 text-sm">
                    {user.roles.join(', ')}
                  </td>
                  <td className="p-3">
                    <button
                      className="flex items-center gap-2 group"
                      onClick={() => {
                        if (isCurrentUser) return;
                        if (user.active) {
                          setUserToDeactivate(user);
                        } else {
                          handleToggleActive(user.id, true);
                        }
                      }}
                      disabled={isCurrentUser}
                      title={statusTitle}
                    >
                      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        user.active ? 'bg-green-500' : 'bg-muted-foreground'
                      }`} />
                      <span className="text-sm text-foreground group-hover:underline">
                        {user.active ? 'Active' : 'Inactive'}
                      </span>
                    </button>
                  </td>
                  <td className="p-3 text-muted-foreground text-sm tabular-nums hidden md:table-cell">
                    {user.dedication != null ? Number(user.dedication).toFixed(2) : '-'}
                  </td>
                  <td className="p-3 text-muted-foreground text-sm hidden md:table-cell">
                    {rates?.find((r) => r.id === user.rate_id)?.code ?? '-'}
                  </td>
                  <td className="p-3 text-muted-foreground text-sm hidden sm:table-cell">
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="p-3">
                    <Button
                      variant="ghost"
                      size="icon"
                      asChild
                    >
                      <Link to={`/admin/users/${user.id}`} title="Edit user">
                        <ChevronRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <AlertDialog open={!!userToDeactivate} onOpenChange={() => setUserToDeactivate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate user</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {userToDeactivate?.email}?
              They will no longer be able to log in.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (userToDeactivate) {
                  handleToggleActive(userToDeactivate.id, false);
                  setUserToDeactivate(null);
                }
              }}
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
