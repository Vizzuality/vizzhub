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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { trackerApi } from '../services/tracker';
import {
  useUpdateInvoice,
  useTransitionInvoice,
  useDeleteInvoice,
} from '../hooks/useInvoices';
import { formatCurrency } from '../utils/constants';
import type { AdminInvoice, InvoiceStatus, AdminInvoiceParams } from '../types/tracker';

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending',
  waiting_for_payment: 'Waiting',
  paid: 'Paid',
};

const STATUS_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'text-foreground',
  pending_to_issue: 'bg-aux-yellow/20 text-aux-yellow',
  waiting_for_payment: 'bg-aux-red/20 text-aux-red',
  paid: 'bg-aux-neon-grass/20 text-aux-neon-grass',
};

const NEXT_STATUS: Record<InvoiceStatus, InvoiceStatus | null> = {
  scheduled: null,
  pending_to_issue: 'waiting_for_payment',
  waiting_for_payment: 'paid',
  paid: null,
};

const NEXT_LABELS: Record<InvoiceStatus, string> = {
  scheduled: '',
  pending_to_issue: 'Mark waiting',
  waiting_for_payment: 'Mark paid',
  paid: '',
};

const ALLOWED_TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  scheduled: [],
  pending_to_issue: ['waiting_for_payment'],
  waiting_for_payment: ['paid', 'pending_to_issue'],
  paid: ['waiting_for_payment'],
};

const HOVER_COLORS = 'bg-muted text-foreground';

const SEARCH_DEBOUNCE_MS = 300;

type SortField = 'status' | 'project' | 'due_date' | 'amount';

function EditableCell({
  value: initial,
  placeholder,
  display,
  inputType = 'text',
  inputClass = 'h-6 text-sm px-1',
  onSave,
}: {
  readonly value: string;
  readonly placeholder?: string;
  readonly display?: string;
  readonly inputType?: string;
  readonly inputClass?: string;
  readonly onSave: (value: string) => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(initial);

  const handleSave = (): void => {
    if (val !== initial) onSave(val);
    setEditing(false);
  };

  if (editing) {
    return (
      <Input
        type={inputType}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onBlur={handleSave}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSave();
          if (e.key === 'Escape') { setVal(initial); setEditing(false); }
        }}
        className={inputClass}
        autoFocus
      />
    );
  }

  return (
    <span
      className="cursor-pointer hover:underline"
      onClick={() => { setVal(initial); setEditing(true); }}
    >
      {display || initial || <span className="text-muted-foreground/50 italic">{placeholder ?? 'edit'}</span>}
    </span>
  );
}

function StatusCell({
  invoice,
  onError,
}: {
  readonly invoice: AdminInvoice;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  const qc = useQueryClient();
  const transitionMutation = useTransitionInvoice(invoice.project_id);
  const next = NEXT_STATUS[invoice.status];

  const handleTransition = (): void => {
    if (!next) return;
    transitionMutation.mutate(
      { invoiceId: invoice.id, status: next },
      {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] });
        },
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? 'Transition failed';
          onError(msg);
        },
      },
    );
  };

  const label = hovered && next ? NEXT_LABELS[invoice.status] : STATUS_LABELS[invoice.status];
  const colors = hovered && next ? HOVER_COLORS : STATUS_COLORS[invoice.status];

  return (
    <button
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium w-[100px] justify-center transition-colors whitespace-nowrap',
        next ? 'cursor-pointer' : 'cursor-default',
        colors,
      )}
      onMouseEnter={() => next && setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleTransition}
      disabled={!next || transitionMutation.isPending}
    >
      {label}
    </button>
  );
}

function InvoiceRow({
  invoice,
  onError,
}: {
  readonly invoice: AdminInvoice;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const qc = useQueryClient();
  const updateMutation = useUpdateInvoice(invoice.project_id);
  const deleteMutation = useDeleteInvoice(invoice.project_id);
  const transitions = ALLOWED_TRANSITIONS[invoice.status];
  const transitionMutation = useTransitionInvoice(invoice.project_id);

  const save = (field: string, value: string): void => {
    const data: Record<string, unknown> = {};
    if (field === 'code') data.code = value || null;
    else if (field === 'amount') data.amount = parseFloat(value) || 0;
    else data[field] = value;
    updateMutation.mutate(
      { invoiceId: invoice.id, data },
      { onSuccess: () => qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] }) },
    );
  };

  return (
    <tr className="border-b last:border-0 text-sm">
      <td className="py-2">
        <Link
          to={`/tracker/projects/${invoice.project_id}`}
          className="hover:underline text-sm font-medium"
        >
          {invoice.project_name}
        </Link>
      </td>
      <td className="py-2">
        <EditableCell
          value={invoice.code ?? ''}
          placeholder="add code"
          onSave={(v) => save('code', v)}
          inputClass="h-6 w-24 text-sm px-1"
        />
      </td>
      <td className="py-2">
        <EditableCell
          value={invoice.milestone}
          onSave={(v) => save('milestone', v)}
          inputClass="h-6 w-full text-sm px-1"
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
        <StatusCell invoice={invoice} onError={onError} />
      </td>
      <td className="py-2 text-right">
        <div className="flex items-center gap-1 justify-end">
          {invoice.status === 'paid' && transitions.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground"
              onClick={() => transitionMutation.mutate(
                { invoiceId: invoice.id, status: transitions[0] },
                { onSuccess: () => qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] }) },
              )}
              disabled={transitionMutation.isPending}
            >
              Revert
            </Button>
          )}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete invoice?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete &quot;{invoice.milestone}&quot;
                  ({formatCurrency(invoice.amount)}) from {invoice.project_name}.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  onClick={() => deleteMutation.mutate(invoice.id, {
                    onSuccess: () => qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] }),
                  })}
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
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
  const Icon = !isActive ? ArrowUpDown : currentOrder === 'asc' ? ArrowUp : ArrowDown;
  return (
    <button
      onClick={() => onClick(field)}
      className={cn(
        'flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
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
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by project name..."
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          <div className="flex items-center gap-1">
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
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
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

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Due:</span>
            <Input
              type="date"
              value={state.due_from}
              onChange={(e) => setState({ due_from: e.target.value, page: '1' })}
              className="w-36 h-8 text-sm"
            />
            <span className="text-muted-foreground">-</span>
            <Input
              type="date"
              value={state.due_to}
              onChange={(e) => setState({ due_to: e.target.value, page: '1' })}
              className="w-36 h-8 text-sm"
            />
          </div>

          <div className="flex items-center gap-1 ml-auto">
            <span className="text-sm text-muted-foreground">Sort:</span>
            <SortButton field="status" label="Status" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="project" label="Project" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="due_date" label="Due Date" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
            <SortButton field="amount" label="Amount" currentField={state.sort_by} currentOrder={state.sort_order} onClick={handleSort} />
          </div>
        </div>
      </div>

      {hasFilters && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/50 text-sm">
          <span className="text-muted-foreground">Filters active</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setState({ status: '', search: '', due_from: '', due_to: '', page: '1' })}
            className="gap-1 h-7 ml-2"
          >
            <X className="w-3.5 h-3.5" />
            Clear all
          </Button>
        </div>
      )}

      {errorMsg && (
        <div className="px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
          {errorMsg}
        </div>
      )}

      <Card className="min-w-0 overflow-hidden">
        <CardContent className="pt-5">
          {items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b">
                    <th className="text-left font-medium pb-2">Project</th>
                    <th className="text-left font-medium pb-2">Code</th>
                    <th className="text-left font-medium pb-2">Milestone</th>
                    <th className="text-right font-medium pb-2 pr-4">Amount</th>
                    <th className="text-left font-medium pb-2 pl-4">Due</th>
                    <th className="text-left font-medium pb-2">Status</th>
                    <th className="w-24" />
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

      {total > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-2">
          <p className="text-sm text-muted-foreground">
            Showing {items.length} of {total} invoices
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setState({ page: String(page - 1) })}
              disabled={page <= 1}
            >
              <ChevronLeft className="w-4 h-4" />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setState({ page: String(page + 1) })}
              disabled={page >= pages}
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
