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
import type { OverviewProjectCandidate } from '../types/portfolio';

interface ProjectPickerProps {
  readonly value: string | null;
  readonly candidates: readonly OverviewProjectCandidate[];
  readonly allProjects: readonly OverviewProjectCandidate[];
  readonly onChange: (projectId: string | null) => void;
}

export function ProjectPicker({
  value,
  candidates,
  allProjects,
  onChange,
}: ProjectPickerProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const options = allProjects.length > 0 ? allProjects : candidates;
  const selected = options.find((o) => o.id === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="w-64 justify-between">
          <span className="truncate">
            {value === null ? 'No project — this row is a program' : (selected?.name ?? 'Select project')}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0">
        <Command>
          <CommandInput placeholder="Search project…" />
          <CommandList>
            <CommandEmpty>No project found.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                value="__skip__"
                onSelect={() => {
                  onChange(null);
                  setOpen(false);
                }}
              >
                <Check className={cn('mr-2 h-4 w-4', value === null ? 'opacity-100' : 'opacity-0')} />
                No project — this row is a program
              </CommandItem>
              {options.map((o) => (
                <CommandItem
                  key={o.id}
                  value={o.name}
                  onSelect={() => {
                    onChange(o.id);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn('mr-2 h-4 w-4', value === o.id ? 'opacity-100' : 'opacity-0')}
                  />
                  {o.name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
