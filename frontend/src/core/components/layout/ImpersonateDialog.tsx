import { useState } from 'react';
import { UserRoundCog } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { useUsers } from '@/core/hooks/useUsers';
import { useAuth } from '@/core/hooks/useAuth';
import { getFullName, getInitials } from '@/utils/formatters';

interface ImpersonateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ImpersonateDialog({
  open,
  onOpenChange,
}: ImpersonateDialogProps): JSX.Element {
  const { data: users, isLoading } = useUsers();
  const auth = useAuth();
  const [search, setSearch] = useState('');

  const handleSelect = async (userId: string): Promise<void> => {
    try {
      await auth.impersonate(userId);
      onOpenChange(false);
      setSearch('');
      window.location.reload();
    } catch (err) {
      console.error('Impersonation failed:', err);
    }
  };

  const filteredUsers = users?.filter(
    (u) => u.id !== auth.user?.id,
  ) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 gap-0 max-w-md">
        <DialogHeader className="px-4 pt-4 pb-2">
          <DialogTitle className="flex items-center gap-2 text-base">
            <UserRoundCog className="h-4 w-4" />
            Impersonate User
          </DialogTitle>
          <DialogDescription>
            Select a user to view the app as them.
          </DialogDescription>
        </DialogHeader>
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search by name or email..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList className="max-h-64">
            <CommandEmpty>
              {isLoading ? 'Loading users...' : 'No users found.'}
            </CommandEmpty>
            <CommandGroup>
              {filteredUsers
                .filter((u) => {
                  const q = search.toLowerCase();
                  if (!q) return true;
                  return getFullName(u.first_name, u.last_name).toLowerCase().includes(q)
                    || u.email.toLowerCase().includes(q);
                })
                .map((u) => {
                  const name = getFullName(u.first_name, u.last_name, u.email);
                  const initials = getInitials(u.first_name, u.last_name);

                  return (
                    <CommandItem
                      key={u.id}
                      value={u.id}
                      onSelect={() => handleSelect(u.id)}
                      className="flex items-center gap-3 px-4 py-2 cursor-pointer"
                    >
                      <Avatar className="h-7 w-7">
                        <AvatarImage src={u.picture ?? undefined} alt={name} />
                        <AvatarFallback className="text-xs">
                          {initials}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm font-medium truncate">{name}</span>
                        <span className="text-xs text-muted-foreground truncate">
                          {u.email}
                        </span>
                      </div>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {u.role}
                      </span>
                    </CommandItem>
                  );
                })}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
