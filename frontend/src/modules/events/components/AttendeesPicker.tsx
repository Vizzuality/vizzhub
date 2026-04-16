import { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useUserSummaries } from '@/core/hooks/useUsers';
import { getFullName } from '@/utils/formatters';
import { useEventOptions } from '../hooks/useEventOptions';
import { ROLE_COLORS } from '../utils/constants';
import type { Attendee } from '../types/events';

type AttendeesPickerProps = {
  readonly eventId: string;
  readonly attendees: Attendee[];
  readonly onAdd: (attendees: { user_id: string; role: string }[]) => void;
  readonly onRemove: (userId: string) => void;
};

export function AttendeesPicker({
  attendees,
  onAdd,
  onRemove,
}: AttendeesPickerProps): JSX.Element {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedRole, setSelectedRole] = useState('Attendee');
  const [userOpen, setUserOpen] = useState(false);

  const { data: users } = useUserSummaries();
  const { data: options } = useEventOptions();
  const roles = options?.attendee_roles ?? [];

  const existingUserIds = useMemo(
    () => new Set(attendees.map((a) => a.user_id)),
    [attendees],
  );

  const availableUsers = useMemo(
    () => (users ?? []).filter((u) => u.active && !existingUserIds.has(u.id)),
    [users, existingUserIds],
  );

  const selectedUser = availableUsers.find((u) => u.id === selectedUserId);

  const handleAdd = (): void => {
    if (!selectedUserId || !selectedRole) return;
    onAdd([{ user_id: selectedUserId, role: selectedRole }]);
    setSelectedUserId('');
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">Attendees</h4>

      {attendees.length > 0 && (
        <div className="space-y-1.5">
          {attendees.map((attendee) => (
            <div
              key={attendee.id}
              className="flex items-center justify-between gap-2 rounded-md border px-3 py-1.5 text-sm"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="truncate">
                  {attendee.user_name ?? attendee.user_email ?? 'Unknown'}
                </span>
                <Badge
                  variant="outline"
                  className="shrink-0 text-xs"
                  style={{
                    borderColor: ROLE_COLORS[attendee.role] ?? '#64748b',
                    color: ROLE_COLORS[attendee.role] ?? '#64748b',
                  }}
                >
                  {attendee.role}
                </Badge>
                {attendee.functional_area && (
                  <span className="text-xs text-muted-foreground shrink-0">
                    {attendee.functional_area}
                  </span>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0"
                onClick={() => onRemove(attendee.user_id)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Popover open={userOpen} onOpenChange={setUserOpen}>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="outline"
                role="combobox"
                aria-expanded={userOpen}
                className="w-full justify-between font-normal h-9 text-sm"
              >
                <span className="truncate">
                  {selectedUser
                    ? getFullName(
                        selectedUser.first_name,
                        selectedUser.last_name,
                        selectedUser.email,
                      )
                    : 'Select user...'}
                </span>
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              className="w-[--radix-popover-trigger-width] p-0"
              align="start"
            >
              <Command>
                <CommandInput placeholder="Search users..." />
                <CommandList>
                  <CommandEmpty>No users found.</CommandEmpty>
                  <CommandGroup>
                    {availableUsers.map((user) => {
                      const name = getFullName(
                        user.first_name,
                        user.last_name,
                        user.email,
                      );
                      return (
                        <CommandItem
                          key={user.id}
                          value={name}
                          onSelect={() => {
                            setSelectedUserId(user.id);
                            setUserOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              'mr-2 h-4 w-4',
                              selectedUserId === user.id
                                ? 'opacity-100'
                                : 'opacity-0',
                            )}
                          />
                          {name}
                        </CommandItem>
                      );
                    })}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>

        <Select value={selectedRole} onValueChange={setSelectedRole}>
          <SelectTrigger className="w-[140px] h-9 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {roles.map((role) => (
              <SelectItem key={role} value={role}>
                {role}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          type="button"
          size="sm"
          className="h-9"
          disabled={!selectedUserId}
          onClick={handleAdd}
        >
          Add
        </Button>
      </div>
    </div>
  );
}
