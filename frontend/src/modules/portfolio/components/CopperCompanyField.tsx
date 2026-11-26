import { useState } from 'react';
import { isAxiosError } from 'axios';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { useCopperCompanies } from '../hooks/useClients';
import type { CopperCompanyOption } from '../types/portfolio';

interface CopperCompanyFieldProps {
  readonly value: number | null;
  readonly onChange: (companyId: number | null) => void;
  readonly clientName: string;
}

function companyLabel(company: CopperCompanyOption): string {
  return company.email_domain ? `${company.name} (${company.email_domain})` : company.name;
}

/** Manual link to a Copper company, for clients the name matching could not resolve. */
export function CopperCompanyField({
  value,
  onChange,
  clientName,
}: CopperCompanyFieldProps): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const { data: companies, error, isLoading } = useCopperCompanies(true);

  if (isAxiosError(error) && error.response?.status === 409) return null;

  const selected = companies?.find((c) => c.id === value);
  let triggerText = 'Not linked';
  if (isLoading) triggerText = 'Loading Copper companies…';
  else if (selected) triggerText = companyLabel(selected);
  else if (value !== null) triggerText = `Copper company ${value}`;

  const select = (companyId: number | null): void => {
    onChange(companyId);
    setOpen(false);
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor="client-copper-company">Copper company</Label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id="client-copper-company"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={isLoading || !!error}
            className="w-full h-8 justify-between font-normal text-sm"
          >
            <span className="truncate">{triggerText}</span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search Copper companies…" />
            <CommandList>
              <CommandEmpty>No Copper company found.</CommandEmpty>
              <CommandGroup>
                <CommandItem value="__not_linked__" onSelect={() => select(null)}>
                  <Check className={cn('mr-2 h-4 w-4', value === null ? 'opacity-100' : 'opacity-0')} />
                  <span className="text-muted-foreground">Not linked</span>
                </CommandItem>
                {(companies ?? []).map((c) => {
                  const takenByOther = c.linked_client_name !== null && c.id !== value;
                  return (
                    <CommandItem
                      key={c.id}
                      value={`${companyLabel(c)} ${c.id}`}
                      disabled={takenByOther}
                      onSelect={() => select(c.id)}
                    >
                      <Check className={cn('mr-2 h-4 w-4', value === c.id ? 'opacity-100' : 'opacity-0')} />
                      <span className="truncate">{companyLabel(c)}</span>
                      {takenByOther && (
                        <span className="ml-auto pl-2 text-xs text-muted-foreground truncate">
                          {c.linked_client_name === clientName ? 'linked' : `→ ${c.linked_client_name}`}
                        </span>
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error && !isLoading && (
        <p className="text-xs text-destructive">Could not read Copper right now.</p>
      )}
    </div>
  );
}
