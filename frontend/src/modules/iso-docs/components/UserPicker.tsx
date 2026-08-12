import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Button } from '@/shared/components/ui/button';
import { useUsers } from '@/core/hooks/useUsers';
import { getFullName } from '@/utils/formatters';

interface UserPickerProps {
  readonly value: string | null;
  readonly onSelect: (name: string) => void;
  readonly onCancel?: () => void;
  readonly defaultOpen?: boolean;
  readonly align?: 'start' | 'center' | 'end';
  readonly triggerClassName?: string;
}

export function UserPicker({
  value,
  onSelect,
  onCancel,
  defaultOpen = false,
  align = 'start',
  triggerClassName = 'w-full justify-between font-normal',
}: UserPickerProps): JSX.Element {
  const [open, setOpen] = useState(defaultOpen);
  const { data: users = [] } = useUsers(true);
  const userNames = users.map((u) => getFullName(u.first_name, u.last_name, u.email));

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        if (!o && onCancel) onCancel();
        setOpen(o);
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className={triggerClassName}>
          {value || 'Select user...'}
          <ChevronsUpDown className="h-4 w-4 ml-2 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align={align}>
        <Command>
          <CommandInput placeholder="Search user..." />
          <CommandList>
            <CommandEmpty>No user found.</CommandEmpty>
            <CommandGroup>
              {userNames.map((name) => (
                <CommandItem
                  key={name}
                  value={name}
                  onSelect={() => {
                    onSelect(name);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={`h-4 w-4 mr-2 ${value === name ? 'opacity-100' : 'opacity-0'}`}
                  />
                  {name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
