import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { cn } from '@/lib/utils';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';
import { useClients } from '../hooks/useClients';
import type { Client } from '../types/portfolio';
import { ClientFormDialog } from '../components/ClientFormDialog';
import { ClientMergeDialog } from '../components/ClientMergeDialog';

const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE = 50;

export default function PortfolioClients(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const { state, setState } = useUrlState({
    page: { defaultValue: '1' },
    search: { defaultValue: '' },
  });
  const page = Number.parseInt(state.page, 10) || 1;

  const [localSearch, setLocalSearch] = useState(state.search);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => setLocalSearch(state.search), [state.search]);

  const handleSearchChange = useCallback(
    (value: string) => {
      setLocalSearch(value);
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(
        () => setState({ search: value, page: '1' }),
        SEARCH_DEBOUNCE_MS,
      );
    },
    [setState],
  );

  const { data, isLoading } = useClients({
    page,
    page_size: PAGE_SIZE,
    ...(state.search && { search: state.search }),
  });

  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => setSelected({}), [page]);
  const [editing, setEditing] = useState<Client | null>(null);
  const [mergeOpen, setMergeOpen] = useState(false);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectedIds = Object.keys(selected).filter((id) => selected[id]);
  const selectedClients = items.filter((c) => selected[c.id]);

  const toggle = (id: string): void => setSelected((s) => ({ ...s, [id]: !s[id] }));

  if (isLoading && !data) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search clients..."
            value={localSearch}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9 h-8"
          />
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            {selectedIds.length >= 2 && (
              <Button size="sm" variant="outline" onClick={() => setMergeOpen(true)}>
                Merge selected ({selectedIds.length})
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus className="w-4 h-4 mr-1" /> New client
            </Button>
          </div>
        )}
      </div>

      <Card className="min-w-0 overflow-hidden">
        <CardContent className="pt-4 pb-3">
          {items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-0">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b">
                    {canManage && <th className="w-8 pb-2" />}
                    <th className="text-left font-medium pb-2">Client</th>
                    <th className="text-left font-medium pb-2">Code</th>
                    <th className="text-right font-medium pb-2 pr-4">Projects</th>
                    <th className="text-left font-medium pb-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr
                      key={c.id}
                      className={cn(
                        'border-b last:border-0 hover:bg-muted/40',
                        canManage && 'cursor-pointer',
                      )}
                      onClick={
                        canManage
                          ? () => {
                              setEditing(c);
                              setFormOpen(true);
                            }
                          : undefined
                      }
                    >
                      {canManage && (
                        <td className="py-2" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={!!selected[c.id]}
                            onChange={() => toggle(c.id)}
                            aria-label={`Select ${c.name}`}
                          />
                        </td>
                      )}
                      <td className="py-2 font-medium text-foreground">{c.name}</td>
                      <td className="py-2 text-xs text-muted-foreground font-mono">{c.slug}</td>
                      <td className="py-2 text-right tabular-nums pr-4">{c.project_count}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className={cn(
                              'inline-block w-2 h-2 rounded-full shrink-0',
                              c.is_active ? 'bg-green-500' : 'bg-muted-foreground',
                            )}
                          />
                          <span className="text-foreground">
                            {c.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm py-4 text-center">No clients</p>
          )}
        </CardContent>
      </Card>

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {items.length} of {total}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setState({ page: String(page - 1) })}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-muted-foreground">
              {page} / {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => setState({ page: String(page + 1) })}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {canManage && (
        <>
          <ClientFormDialog open={formOpen} onOpenChange={setFormOpen} client={editing} />
          <ClientMergeDialog
            open={mergeOpen}
            onOpenChange={setMergeOpen}
            candidates={selectedClients}
            onMerged={() => setSelected({})}
          />
        </>
      )}
    </div>
  );
}
