import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import type { ProgramAction } from '../types/portfolio';
import type { ProgramOption } from '../hooks/useOverviewImport';

interface ProgramPickerProps {
  readonly action: ProgramAction;
  readonly programId: string | null;
  readonly inheritedName: string | null;
  readonly programs: readonly ProgramOption[];
  readonly onLink: (programId: string) => void;
  readonly onCreate: () => void;
  readonly onNone: () => void;
}

export function ProgramPicker(props: ProgramPickerProps): JSX.Element {
  const { action, programId, inheritedName, programs, onLink, onCreate, onNone } = props;
  const [open, setOpen] = useState(false);

  if (action === 'inherit') {
    return (
      <span className="text-sm text-muted-foreground">Inherited: {inheritedName ?? '—'}</span>
    );
  }

  const label =
    action === 'create'
      ? 'Create new program'
      : action === 'none'
        ? 'Keep none'
        : (programs.find((p) => p.id === programId)?.name ?? 'Select program');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="w-64 justify-between">
          <span className="truncate">{label}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0">
        <Command>
          <CommandInput placeholder="Search program…" />
          <CommandList>
            <CommandEmpty>No program found.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                value="__create__"
                onSelect={() => {
                  onCreate();
                  setOpen(false);
                }}
              >
                <Check
                  className={cn(
                    'mr-2 h-4 w-4',
                    action === 'create' ? 'opacity-100' : 'opacity-0',
                  )}
                />
                Create new program
              </CommandItem>
              <CommandItem
                value="__none__"
                onSelect={() => {
                  onNone();
                  setOpen(false);
                }}
              >
                <Check
                  className={cn(
                    'mr-2 h-4 w-4',
                    action === 'none' ? 'opacity-100' : 'opacity-0',
                  )}
                />
                Keep none
              </CommandItem>
              {programs.map((p) => (
                <CommandItem
                  key={p.id}
                  value={p.name}
                  onSelect={() => {
                    onLink(p.id);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      programId === p.id ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  {p.name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
