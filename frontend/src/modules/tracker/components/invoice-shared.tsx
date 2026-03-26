import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
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
import { Trash2, PauseCircle, History } from 'lucide-react';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/core/hooks/queryKeys';
import {
  useUpdateInvoice,
  useTransitionInvoice,
  useDeleteInvoice,
} from '../hooks/useInvoices';
import { trackerApi } from '../services/tracker';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import type { Invoice, InvoiceStatus, Postponement } from '../types/tracker';

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending',
  postponed: 'Postponed',
  waiting_for_payment: 'Waiting',
  paid: 'Paid',
};

export const STATUS_DOT_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'bg-muted-foreground',
  pending_to_issue: 'bg-aux-yellow',
  postponed: 'bg-orange-400',
  waiting_for_payment: 'bg-aux-red',
  paid: 'bg-aux-neon-grass',
};

const NEXT_STATUS: Record<InvoiceStatus, InvoiceStatus | null> = {
  scheduled: null,
  pending_to_issue: 'waiting_for_payment',
  postponed: null,
  waiting_for_payment: 'paid',
  paid: null,
};

const NEXT_LABELS: Record<InvoiceStatus, string> = {
  scheduled: '',
  pending_to_issue: 'Mark waiting',
  postponed: '',
  waiting_for_payment: 'Mark paid',
  paid: '',
};

export const ALLOWED_TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  scheduled: [],
  pending_to_issue: ['waiting_for_payment'],
  postponed: [],
  waiting_for_payment: ['paid', 'pending_to_issue'],
  paid: ['waiting_for_payment'],
};

export function getDisplayDate(invoice: { status: string; postponed_to?: string | null; due_date: string }): string {
  return invoice.status === 'postponed' && invoice.postponed_to ? invoice.postponed_to : invoice.due_date;
}

export function EditableCell({
  value: initial,
  placeholder,
  display,
  displayClass,
  inputType = 'text',
  inputClass = 'h-6 text-sm px-1',
  onSave,
}: {
  readonly value: string;
  readonly placeholder?: string;
  readonly display?: string;
  readonly displayClass?: string;
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

  const startEditing = (): void => { setVal(initial); setEditing(true); };

  return (
    <span
      role="button"
      tabIndex={0}
      className={cn('cursor-pointer hover:underline', displayClass)}
      onClick={startEditing}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEditing(); } }}
      title={display || initial || undefined}
    >
      {display || initial || (
        <span className="text-muted-foreground italic">{placeholder ?? 'edit'}</span>
      )}
    </span>
  );
}

export function StatusCell({
  invoice,
  currency = 'euro',
  onError,
  onSuccess,
}: {
  readonly invoice: Invoice;
  readonly currency?: string;
  readonly onError: (msg: string) => void;
  readonly onSuccess?: () => void;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const transitionMutation = useTransitionInvoice(invoice.project_id);
  const next = NEXT_STATUS[invoice.status];

  const doTransition = (): void => {
    if (!next) return;
    transitionMutation.mutate(
      { invoiceId: invoice.id, status: next },
      {
        onSuccess: () => { setConfirming(false); onSuccess?.(); },
        onError: (err: unknown) => {
          setConfirming(false);
          const msg = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? 'Transition failed';
          onError(msg);
        },
      },
    );
  };

  const label = hovered && next ? NEXT_LABELS[invoice.status] : STATUS_LABELS[invoice.status];
  return (
    <>
      <button
        className={cn(
          'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium text-foreground transition-colors whitespace-nowrap w-[90px]',
          next ? 'cursor-pointer hover:bg-muted/50' : 'cursor-default',
        )}
        onMouseEnter={() => next && setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => next && setConfirming(true)}
        disabled={!next || transitionMutation.isPending}
      >
        <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', STATUS_DOT_COLORS[invoice.status])} />
        {label}
      </button>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change invoice status?</AlertDialogTitle>
            <AlertDialogDescription>
              Move &quot;{invoice.milestone}&quot; ({formatCurrency(invoice.amount, currency, 2)})
              {' '}from {STATUS_LABELS[invoice.status]} to {next ? STATUS_LABELS[next] : ''}?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doTransition} disabled={transitionMutation.isPending}>
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function PostponeButton({
  invoice,
  currency = 'euro',
  onError,
  onSuccess,
}: {
  readonly invoice: Invoice;
  readonly currency?: string;
  readonly onError: (msg: string) => void;
  readonly onSuccess?: () => void;
}): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const [newDate, setNewDate] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (invoice.status !== 'pending_to_issue') return null;

  const baseDate = invoice.postponed_to ?? invoice.due_date;
  const base = new Date(baseDate + 'T00:00:00');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const minDate = new Date(base);
  minDate.setDate(minDate.getDate() + 1);
  if (minDate < today) {
    minDate.setTime(today.getTime());
    minDate.setDate(minDate.getDate() + 1);
  }
  const maxRef = base > today ? base : today;
  const maxDate = new Date(maxRef);
  maxDate.setDate(maxDate.getDate() + 30);

  const fmt = (d: Date): string => d.toISOString().split('T')[0];

  const handlePostpone = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault();
    if (!newDate || !reason.trim()) return;
    setSubmitting(true);
    try {
      await trackerApi.postponeInvoice(invoice.project_id, invoice.id, {
        postponed_to: newDate,
        reason: reason.trim(),
      });
      setOpen(false);
      setNewDate('');
      setReason('');
      onSuccess?.();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Postpone failed';
      onError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <button
          className="text-muted-foreground hover:text-foreground transition-colors p-1"
          title="Postpone"
        >
          <PauseCircle className="w-4 h-4" />
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Postpone invoice</AlertDialogTitle>
          <AlertDialogDescription>
            {invoice.milestone} ({formatCurrency(invoice.amount, currency, 2)})
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 py-2">
          <div className="text-xs text-muted-foreground">
            Base date: {baseDate} &middot; Limit: {fmt(maxDate)}
          </div>
          <Input
            type="date"
            value={newDate}
            min={fmt(minDate)}
            max={fmt(maxDate)}
            onChange={(e) => setNewDate(e.target.value)}
            className="h-8 text-sm"
          />
          <Textarea
            placeholder="Reason for postponement..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="text-sm min-h-[60px]"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handlePostpone}
            disabled={submitting || !newDate || !reason.trim()}
          >
            Postpone
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function PostponementHistory({
  projectId,
  invoiceId,
  expanded,
  colSpan,
  onDelete,
}: {
  readonly projectId: string;
  readonly invoiceId: string;
  readonly expanded: boolean;
  readonly colSpan: number;
  readonly onDelete?: () => void;
}): JSX.Element | null {
  const { data, refetch } = useQuery({
    queryKey: queryKeys.tracker.invoices.postponements(projectId, invoiceId),
    queryFn: () => trackerApi.listPostponements(projectId, invoiceId),
    enabled: expanded,
  });
  const [deleting, setDeleting] = useState(false);

  if (!expanded || !data || data.length === 0) return null;

  const handleDelete = async (): Promise<void> => {
    setDeleting(true);
    try {
      await trackerApi.deleteLatestPostponement(projectId, invoiceId);
      await refetch();
      onDelete?.();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <tr className="bg-muted/30">
      <td colSpan={colSpan} className="px-4 py-2">
        <div className="space-y-1.5">
          {data.map((p: Postponement, idx: number) => (
            <div key={p.id} className="flex items-center gap-3 text-xs">
              <span className="text-muted-foreground shrink-0 tabular-nums">{p.postponed_to}</span>
              <span className="text-foreground flex-1">{p.reason}</span>
              <span className="text-muted-foreground/60 shrink-0">
                {new Date(p.created_at).toLocaleDateString()}
              </span>
              {idx === 0 && (
                <button
                  className="text-muted-foreground hover:text-destructive transition-colors shrink-0 p-0.5 disabled:opacity-50"
                  title="Remove last postponement"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}

export function HistoryToggle({
  count,
  expanded,
  onToggle,
}: {
  readonly count: number;
  readonly expanded: boolean;
  readonly onToggle: () => void;
}): JSX.Element | null {
  if (count === 0) return null;

  return (
    <button
      className={cn(
        'text-muted-foreground hover:text-foreground transition-colors p-0.5',
        expanded && 'text-foreground',
      )}
      onClick={onToggle}
      title={`${count} postponement${count > 1 ? 's' : ''}`}
    >
      <History className="w-3.5 h-3.5" />
    </button>
  );
}

export function RevertButton({
  invoice,
  onSuccess,
}: {
  readonly invoice: Invoice;
  readonly onSuccess?: () => void;
}): JSX.Element | null {
  const transitions = ALLOWED_TRANSITIONS[invoice.status];
  const transitionMutation = useTransitionInvoice(invoice.project_id);

  if (invoice.status !== 'paid' || transitions.length === 0) return null;

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground">
          Revert
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revert invoice?</AlertDialogTitle>
          <AlertDialogDescription>
            Move &quot;{invoice.milestone}&quot; back to {STATUS_LABELS[transitions[0]]}?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => transitionMutation.mutate(
              { invoiceId: invoice.id, status: transitions[0] },
              { onSuccess },
            )}
            disabled={transitionMutation.isPending}
          >
            Confirm
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function DeleteButton({
  invoice,
  projectId,
  currency = 'euro',
  onSuccess,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
  readonly currency?: string;
  readonly onSuccess?: () => void;
}): JSX.Element {
  const deleteMutation = useDeleteInvoice(projectId);

  return (
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
            ({formatCurrency(invoice.amount, currency, 2)}). This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={() => deleteMutation.mutate(invoice.id, { onSuccess })}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function useInvoiceFieldSave(
  projectId: string,
  invoiceId: string,
  onSuccess?: () => void,
): (field: string, value: string) => void {
  const updateMutation = useUpdateInvoice(projectId);
  return (field: string, value: string) => {
    const data: Record<string, unknown> = {};
    if (field === 'code') data.code = value || null;
    else if (field === 'amount') data.amount = Number.parseFloat(value) || 0;
    else data[field] = value;
    updateMutation.mutate({ invoiceId, data }, { onSuccess });
  };
}
