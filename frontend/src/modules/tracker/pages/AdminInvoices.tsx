import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { cn } from '@/lib/utils';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { trackerApi } from '../services/tracker';
import { formatCurrency } from '../utils/constants';
import {
  EditableCell,
  StatusCell,
  RevertButton,
  DeleteButton,
  useInvoiceFieldSave,
} from '../components/invoice-shared';
import type { AdminInvoice, AdminInvoiceParams } from '../types/tracker';

const SEARCH_DEBOUNCE_MS = 300;
type SortField = 'status' | 'project' | 'due_date' | 'amount';

function InvoiceRow({
  invoice,
  onError,
}: {
  readonly invoice: AdminInvoice;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const qc = useQueryClient();
  const invalidate = useCallback(
    () => { qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] }); },
    [qc],
  );
  const save = useInvoiceFieldSave(invoice.project_id, invoice.id, invalidate);

  return (
    <tr className="border-b last:border-0 text-sm">
      <td className="py-2 pr-4 max-w-[140px]">
        <Link
          to={`/tracker/projects/${invoice.project_id}`}
          className="hover:underline font-medium text-sm leading-tight block"
        >
          {invoice.project_name}
        </Link>
      </td>
      <td className="py-2 max-w-[200px]">
        <EditableCell
          value={invoice.milestone}
          display={invoice.milestone}
          displayClass="truncate block max-w-[200px]"
          onSave={(v) => save('milestone', v)}
          inputClass="h-6 w-full text-sm px-1"
        />
      </td>
      <td className="py-2">
        <EditableCell
          value={invoice.code ?? ''}
          placeholder="add code"
          onSave={(v) => save('code', v)}
          inputClass="h-6 w-24 text-sm px-1"
        />
      </td>
      <td className="py-2 text-right tabular-nums pr-4">
        <EditableCell
          value={invoice.amount.toString()}
          display={formatCurrency(invoice.amount)}
          inputType="number"
          onSave={(v) => save('amount', v)}
          inputClass="h-6 w-24 text-sm px-1 text-right"
        />
      </td>
      <td className="py-2 pl-4">
        <EditableCell
          value={invoice.due_date}
          inputType="date"
          onSave={(v) => save('due_date', v)}
          inputClass="h-6 w-36 text-sm px-1"
        />
      </td>
      <td className="py-2">
        <StatusCell invoice={invoice} onError={onError} onSuccess={invalidate} />
      </td>
      <td className="py-2 text-right">
        <div className="flex items-center gap-1 justify-end">
          <RevertButton invoice={invoice} onSuccess={invalidate} />
          <DeleteButton invoice={invoice} projectId={invoice.project_id} onSuccess={invalidate} />
        </div>
      </td>
    </tr>
  );
}

function SortButton({
  field,
  label,
  currentField,
  currentOrder,
  onClick,
}: {
  readonly field: SortField;
  readonly label: string;
  readonly currentField: string;
  readonly currentOrder: string;
  readonly onClick: (field: SortField) => void;
}): JSX.Element {
  const isActive = currentField === field;
  const activeIcon = currentOrder === 'asc' ? ArrowUp : ArrowDown;
  const Icon = isActive ? activeIcon : ArrowUpDown;
  return (
    <button
      onClick={() => onClick(field)}
      className={cn(
        'flex items-center gap-1 px-2 py-1 text-sm font-medium rounded-md transition-colors',
        isActive
          ? 'bg-muted text-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
      )}
    >
      {label}
      <Icon className="w-3.5 h-3.5" />
    </button>
  );
}

export default function AdminInvoices(): JSX.Element {
  const { state, setState } = useUrlState({
    page: { defaultValue: '1' },
    status: { defaultValue: '' },
    search: { defaultValue: '' },
    due_from: { defaultValue: '' },
    due_to: { defaultValue: '' },
    sort_by: { defaultValue: 'status' },
    sort_order: { defaultValue: 'asc' },
  });

  const page = parseInt(state.page, 10) || 1;
  const [localSearch, setLocalSearch] = useState(state.search);

  useEffect(() => { setLocalSearch(state.search); }, [state.search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== state.search) {
        setState({ search: localSearch, page: '1' });
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, state.search, setState]);

  const params: AdminInvoiceParams = {
    page,
    page_size: 50,
    ...(state.status && { status: state.status }),
    ...(state.search && { search: state.search }),
    ...(state.due_from && { due_from: state.due_from }),
    ...(state.due_to && { due_to: state.due_to }),
    sort_by: state.sort_by,
    sort_order: state.sort_order,
  };

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.tracker.invoices.all(params as unknown as Record<string, unknown>),
    queryFn: () => trackerApi.listAllInvoices(params),
  });

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const showError = useCallback((msg: string) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 5000);
  }, []);

  const handleSort = (field: SortField): void => {
    if (state.sort_by === field) {
      setState({ sort_order: state.sort_order === 'asc' ? 'desc' : 'asc', page: '1' });
    } else {
      setState({ sort_by: field, sort_order: 'asc', page: '1' });
    }
  };

  const hasFilters = state.status || state.search || state.due_from || state.due_to;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  if (isLoading && !data) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search project..."
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="pl-9 h-8"
            />
          </div>

          <div className="flex items-center gap-1 flex-wrap">
            {([
              { value: '', label: 'All' },
              { value: 'pending_to_issue', label: 'Pending' },
              { value: 'waiting_for_payment', label: 'Waiting' },
              { value: 'scheduled', label: 'Scheduled' },
              { value: 'paid', label: 'Paid' },
            ] as const).map((opt) => (
              <button
                key={opt.value}
                onClick={() => setState({ status: opt.value, page: '1' })}
                className={cn(
                  'px-2 py-1 text-sm font-medium rounded-md transition-colors',
                  state.status === opt.value
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Due:</span>
            <Input type="date" value={state.due_from} onChange={(e) => setState({ due_from: e.target.value, page: '1' })} className="w-40 h-8 text-sm" />
            <span className="text-muted-foreground">-</span>
            <Input type="date" value={state.due_to} onChange={(e) => setState({ due_to: e.target.value, page: '1' })} className="w-40 h-8 text-sm" />
          </div>

          <div className="flex items-center gap-1 ml-auto">
            <SortButton field="status" label="Status" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="project" label="Project" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="due_date" label="Due" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="amount" label="Amount" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
          </div>
        </div>
      </div>

      {hasFilters && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/50 text-sm">
          <span className="text-muted-foreground">Filters active</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setState({ status: '', search: '', due_from: '', due_to: '', page: '1' })}
            className="gap-1 h-6 ml-2"
          >
            <X className="w-3 h-3" />
            Clear
          </Button>
        </div>
      )}

      {errorMsg && (
        <div className="px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
          {errorMsg}
        </div>
      )}

      {/* Table */}
      <Card className="min-w-0 overflow-hidden">
        <CardContent className="pt-4 pb-3">
          {items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b">
                    <th className="text-left font-medium pb-2 max-w-[140px]">Project</th>
                    <th className="text-left font-medium pb-2">Milestone</th>
                    <th className="text-left font-medium pb-2">Code</th>
                    <th className="text-right font-medium pb-2 pr-4">Amount</th>
                    <th className="text-left font-medium pb-2 pl-4">Due</th>
                    <th className="text-left font-medium pb-2">Status</th>
                    <th className="w-20" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((inv) => (
                    <InvoiceRow key={inv.id} invoice={inv} onError={showError} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm py-4 text-center">
              {hasFilters ? 'No invoices match your filters' : 'No invoices'}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {items.length} of {total}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setState({ page: String(page - 1) })} disabled={page <= 1}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-sm text-muted-foreground">{page} / {pages}</span>
            <Button variant="outline" size="sm" onClick={() => setState({ page: String(page + 1) })} disabled={page >= pages}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
