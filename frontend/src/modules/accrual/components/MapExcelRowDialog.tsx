import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, Search } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Input } from '@/shared/components/ui/input';
import { useAllProjectSummaries } from '@/core/hooks/useProjects';
import { useCreateAlias } from '@/modules/accrual/hooks/useUnmatched';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import type { AccrualExcelRow } from '@/modules/accrual/types/accrual';
import type { ProjectSummary } from '@/core/types/project';

interface MapExcelRowDialogProps {
  readonly row: AccrualExcelRow | null;
  readonly onOpenChange: (open: boolean) => void;
}

const MATCH_LIMIT = 100;

function filterProjects(projects: ProjectSummary[], q: string): ProjectSummary[] {
  if (!q.trim()) return projects.slice(0, MATCH_LIMIT);
  const needle = q.toLowerCase();
  return projects
    .filter(
      (p) =>
        p.name.toLowerCase().includes(needle) ||
        (p.code ?? '').toLowerCase().includes(needle),
    )
    .slice(0, MATCH_LIMIT);
}

function formatDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) return '';
  return `${start ?? '?'} → ${end ?? '?'}`;
}

function formatBudget(
  budget: number | string | null | undefined,
  currency: string | null | undefined,
): string {
  if (budget === null || budget === undefined || budget === '') return '';
  const n = typeof budget === 'string' ? Number.parseFloat(budget) : budget;
  if (Number.isNaN(n)) return '';
  return formatCurrency(n, currency ?? 'EUR', 0);
}

export function MapExcelRowDialog({ row, onOpenChange }: MapExcelRowDialogProps): JSX.Element {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { data: projects, isLoading: projectsLoading } = useAllProjectSummaries();
  const create = useCreateAlias();

  useEffect(() => {
    if (row) {
      setProject(null);
      setQuery('');
      setError(null);
    }
  }, [row]);

  const filtered = useMemo(
    () => filterProjects(projects ?? [], query),
    [projects, query],
  );

  const isOpen = row !== null;

  const submit = async (): Promise<void> => {
    if (!row || !project) return;
    setError(null);
    try {
      await create.mutateAsync({
        excel_code: row.excel_code,
        project_id: project.id,
      });
      onOpenChange(false);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to create alias';
      setError(msg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Map Excel row to project</DialogTitle>
          <DialogDescription>
            Create a persistent alias so the importer resolves{' '}
            <span className="font-mono">{row?.excel_code}</span> to the chosen tracker project on
            future runs.
          </DialogDescription>
        </DialogHeader>

        <div className="min-w-0 space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>Excel row</Label>
            <div className="rounded border border-border bg-muted/30 px-3 py-2 text-sm">
              <div>
                <span className="font-mono">{row?.excel_code}</span>
                {row?.name ? <span className="text-muted-foreground"> — {row.name}</span> : null}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                {formatDateRange(row?.start_date, row?.end_date)}
                {row?.value_eur && (Number(row.value_eur) > 0) ? (
                  <>
                    {formatDateRange(row?.start_date, row?.end_date) ? ' • ' : ''}
                    {formatBudget(row.value_eur, 'EUR')}
                  </>
                ) : null}
                {row?.pm_name ? (
                  <>
                    {' • PM '}
                    <span className="text-foreground/80">{row.pm_name}</span>
                  </>
                ) : null}
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="alias-project-search">Tracker project</Label>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="alias-project-search"
                placeholder={projectsLoading ? 'Loading projects…' : 'Search by code or name…'}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-8"
                disabled={projectsLoading}
              />
            </div>
            <div className="max-h-64 w-full overflow-y-auto overflow-x-hidden rounded border border-border bg-popover">
              {filtered.length === 0 ? (
                <p className="px-3 py-4 text-center text-sm text-muted-foreground">
                  No project matches.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {filtered.map((p) => {
                    const selected = project?.id === p.id;
                    const dateLine = formatDateRange(p.start_date, p.end_date);
                    const budgetLine = formatBudget(p.budget, p.currency);
                    const meta = [dateLine, budgetLine].filter(Boolean).join(' • ');
                    return (
                      <li key={p.id} className="min-w-0">
                        <button
                          type="button"
                          onClick={() => setProject(p)}
                          className={`flex w-full min-w-0 items-start gap-2 px-3 py-2 text-left text-sm hover:bg-accent ${selected ? 'bg-accent' : ''}`}
                        >
                          <Check className={`mt-0.5 h-4 w-4 shrink-0 ${selected ? 'opacity-100' : 'opacity-0'}`} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-baseline gap-2">
                              <span className="font-mono text-xs text-muted-foreground w-28 shrink-0 truncate">
                                {p.code ?? '—'}
                              </span>
                              <span className="min-w-0 flex-1 truncate">{p.name}</span>
                            </div>
                            {meta && (
                              <div className="ml-[7.5rem] mt-0.5 text-xs text-muted-foreground tabular-nums truncate">
                                {meta}
                              </div>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {(projects?.length ?? 0) > filtered.length && (
                <p className="px-3 py-2 text-xs text-muted-foreground border-t border-border">
                  Showing {filtered.length} of {projects?.length}. Refine the search to narrow down.
                </p>
              )}
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!project || create.isPending}>
            {create.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create alias
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
