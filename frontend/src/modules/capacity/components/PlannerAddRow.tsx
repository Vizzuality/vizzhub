import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';

interface SelectOption {
  id: string;
  name: string;
  extra?: string;
}

interface PlannerAddRowProps {
  readonly options: SelectOption[];
  readonly existingIds: Set<string>;
  readonly onSelect: (id: string) => void;
  readonly label: string;
}

export function PlannerAddRow({
  options,
  existingIds,
  onSelect,
  label,
}: PlannerAddRowProps): JSX.Element {
  const [open, setOpen] = useState(false);

  const available = options
    .filter((o) => !existingIds.has(o.id))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs text-muted-foreground">
          <Plus className="h-3 w-3" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          <CommandList>
            <CommandEmpty>No results</CommandEmpty>
            {available.map((opt) => (
              <CommandItem
                key={opt.id}
                onSelect={() => {
                  onSelect(opt.id);
                  setOpen(false);
                }}
              >
                <span>{opt.name}</span>
                {opt.extra && (
                  <span className="ml-auto text-xs text-muted-foreground">{opt.extra}</span>
                )}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
