import { useState } from 'react';
import { isAxiosError } from 'axios';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import {
  useAllProjectSummaries,
  useCopperOpportunities,
  useLinkCopperOpportunity,
} from '@/core/hooks/useProjects';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import type { CopperOpportunity, CopperOpportunityGroup, CopperProjectRef } from '@/core/types/copper';

interface CopperOpportunityPickerProps {
  readonly onImport: (opportunity: CopperOpportunity) => void;
}

interface OpportunityRowProps {
  readonly opportunity: CopperOpportunity;
  readonly onImport: (opportunity: CopperOpportunity) => void;
}

const GROUPS: { key: CopperOpportunityGroup; title: string }[] = [
  { key: 'pending_signature', title: 'Pending signature' },
  { key: 'signed', title: 'Signed, not in VizzHub' },
];

function describeOpportunity(opportunity: CopperOpportunity): string {
  const parts = [
    opportunity.company_name,
    opportunity.code,
    opportunity.original_budget !== null && opportunity.currency
      ? formatCurrency(opportunity.original_budget, opportunity.currency)
      : null,
    opportunity.stage_changed_on ? `since ${opportunity.stage_changed_on}` : null,
  ];
  return parts.filter(Boolean).join(' · ');
}

interface ProjectLinkPopoverProps {
  readonly disabled: boolean;
  readonly onSelect: (project: CopperProjectRef) => void;
}

function ProjectLinkPopover({ disabled, onSelect }: ProjectLinkPopoverProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const { data: projects, isLoading } = useAllProjectSummaries(open);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" size="sm" variant="ghost" disabled={disabled}>
          Link to a project…
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <Command>
          <CommandInput placeholder="Search projects…" />
          <CommandList>
            <CommandEmpty>{isLoading ? 'Loading projects…' : 'No project found.'}</CommandEmpty>
            <CommandGroup>
              {(projects ?? []).map((p) => (
                <CommandItem
                  key={p.id}
                  value={`${p.name} ${p.code ?? ''} ${p.id}`}
                  onSelect={() => {
                    setOpen(false);
                    onSelect({ id: p.id, name: p.name });
                  }}
                >
                  <span className="truncate">{p.name}</span>
                  {p.code && (
                    <span className="ml-auto pl-2 text-xs text-muted-foreground font-mono truncate">
                      {p.code}
                    </span>
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

function OpportunityRow({ opportunity, onImport }: OpportunityRowProps): JSX.Element {
  const link = useLinkCopperOpportunity();
  const [target, setTarget] = useState<CopperProjectRef | null>(null);
  const linked = opportunity.linked_projects;
  const { suggestion } = opportunity;

  const linkTo = (project: CopperProjectRef): void => {
    setTarget(project);
    link.mutate({ projectId: project.id, opportunityId: opportunity.opportunity_id });
  };

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-border last:border-b-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground truncate">{opportunity.name}</p>
        <p className="text-xs text-muted-foreground font-mono tabular-nums truncate">
          {describeOpportunity(opportunity)}
        </p>
        {linked.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Already in VizzHub: {linked.map((p) => p.name).join(', ')}
          </p>
        )}
        {link.isError && (
          <p className="text-xs text-destructive">Could not link it to {target?.name}.</p>
        )}
      </div>
      {linked.length === 0 && (
        <div className="flex items-center gap-2 shrink-0">
          {suggestion && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={link.isPending}
              onClick={() => linkTo(suggestion)}
            >
              It is {suggestion.name}
            </Button>
          )}
          <ProjectLinkPopover disabled={link.isPending} onSelect={linkTo} />
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Import ${opportunity.name}`}
            onClick={() => onImport(opportunity)}
          >
            Import
          </Button>
        </div>
      )}
    </li>
  );
}

function isNotConnected(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 409;
}

export function CopperOpportunityPicker({
  onImport,
}: CopperOpportunityPickerProps): JSX.Element | null {
  const { data, error, isLoading } = useCopperOpportunities();

  // Render nothing until Copper answers: unconnected setups must not flash the card.
  if (isLoading || isNotConnected(error)) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Import from Copper</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <p className="text-sm text-destructive">Could not read Copper right now.</p>
        )}
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No deals waiting to become a project.</p>
        )}
        {data &&
          GROUPS.map(({ key, title }) => {
            const items = data.filter((o) => o.group === key);
            if (items.length === 0) return null;
            return (
              <div key={key}>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {title}
                </p>
                <ul>
                  {items.map((o) => (
                    <OpportunityRow key={o.opportunity_id} opportunity={o} onImport={onImport} />
                  ))}
                </ul>
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
}
