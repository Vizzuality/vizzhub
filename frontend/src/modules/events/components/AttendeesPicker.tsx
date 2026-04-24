import { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
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

export interface LocalAttendee {
  user_id: string;
  role: string;
  cost: number | null;
  _persistedId?: string;
  user_name?: string | null;
  user_email?: string | null;
  functional_area?: string | null;
}

interface AttendeesPickerProps {
  readonly attendees: LocalAttendee[];
  readonly onChange: (next: LocalAttendee[]) => void;
}

export function AttendeesPicker({
  attendees,
  onChange,
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
    if (!selectedUserId) return;
    const user = availableUsers.find((u) => u.id === selectedUserId);
    onChange([
      ...attendees,
      {
        user_id: selectedUserId,
        role: selectedRole,
        cost: null,
        user_name: user
          ? getFullName(user.first_name, user.last_name, user.email)
          : null,
      },
    ]);
    setSelectedUserId('');
  };

  const updateAttendee = (
    userId: string,
    patch: Partial<LocalAttendee>,
  ): void => {
    onChange(
      attendees.map((a) =>
        a.user_id === userId ? { ...a, ...patch } : a,
      ),
    );
  };

  const removeAttendee = (userId: string): void => {
    onChange(attendees.filter((a) => a.user_id !== userId));
  };

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">Attendees</h4>

      {attendees.length > 0 && (
        <div className="space-y-1.5">
          {attendees.map((a) => (
            <div
              key={a.user_id}
              className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
            >
              <span className="flex-1 truncate">
                {a.user_name ?? a.user_email ?? 'Unknown'}
              </span>
              <Select
                value={a.role}
                onValueChange={(v) => updateAttendee(a.user_id, { role: v })}
              >
                <SelectTrigger className="w-[130px] h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="—"
                className="w-[100px] h-8 text-xs"
                value={a.cost ?? ''}
                onChange={(e) => {
                  const val = e.target.value;
                  updateAttendee(a.user_id, {
                    cost: val === '' ? null : Number(val),
                  });
                }}
                aria-label="Cost"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={() => removeAttendee(a.user_id)}
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
