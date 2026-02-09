import { useState } from 'react';
import { Check, ChevronsUpDown, Lock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import type { SlackChannel } from '@/types';

interface SlackChannelComboboxProps {
  readonly id?: string;
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly channels: SlackChannel[];
  readonly disabled?: boolean;
  readonly placeholder?: string;
  readonly includeNone?: boolean;
  readonly className?: string;
}

export function SlackChannelCombobox({
  id,
  value,
  onValueChange,
  channels,
  disabled = false,
  placeholder = 'Select channel',
  includeNone = false,
  className,
}: SlackChannelComboboxProps): JSX.Element {
  const [open, setOpen] = useState(false);

  const selectedChannel = channels.find((c) => c.id === value);
  let displayLabel = placeholder;
  if (selectedChannel) {
    displayLabel = `#${selectedChannel.name}`;
  } else if (includeNone && !value && channels.length > 0) {
    displayLabel = 'None';
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn('justify-between font-normal', className)}
        >
          <span className="truncate">{displayLabel}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search channels..." />
          <CommandList>
            <CommandEmpty>No channel found.</CommandEmpty>
            <CommandGroup>
              {includeNone && (
                <CommandItem
                  value="__none__"
                  onSelect={() => {
                    onValueChange('');
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn('mr-2 h-4 w-4', !value ? 'opacity-100' : 'opacity-0')}
                  />
                  <span className="text-muted-foreground">None</span>
                </CommandItem>
              )}
              {channels.map((channel) => (
                <CommandItem
                  key={channel.id}
                  value={channel.name}
                  onSelect={() => {
                    onValueChange(channel.id);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      value === channel.id ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  #{channel.name}
                  {channel.is_private && (
                    <Lock className="ml-1 h-3 w-3 text-muted-foreground" />
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
