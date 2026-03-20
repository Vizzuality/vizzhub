import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
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
import {
  useUpdateInvoice,
  useTransitionInvoice,
  useDeleteInvoice,
} from '../hooks/useInvoices';
import { formatCurrency } from '../utils/constants';
import type { InvoiceStatus } from '../types/tracker';

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending',
  waiting_for_payment: 'Waiting',
  paid: 'Paid',
};

export const STATUS_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'text-foreground',
  pending_to_issue: 'bg-aux-yellow/20 text-aux-yellow',
  waiting_for_payment: 'bg-aux-red/20 text-aux-red',
  paid: 'bg-aux-neon-grass/20 text-aux-neon-grass',
};

const HOVER_COLORS = 'bg-muted text-foreground';

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

export const ALLOWED_TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  scheduled: [],
  pending_to_issue: ['waiting_for_payment'],
  waiting_for_payment: ['paid', 'pending_to_issue'],
  paid: ['waiting_for_payment'],
};

// -- EditableCell --

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

  return (
    <span
      className={cn('cursor-pointer hover:underline', displayClass)}
      onClick={() => { setVal(initial); setEditing(true); }}
      title={display || initial || undefined}
    >
      {display || initial || (
        <span className="text-muted-foreground/30 italic">{placeholder ?? 'edit'}</span>
      )}
    </span>
  );
}

// -- StatusCell with confirmation dialog --

interface BaseInvoice {
  id: string;
  project_id: string;
  code: string | null;
  amount: number;
  milestone: string;
  due_date: string;
  status: InvoiceStatus;
}

export function StatusCell({
  invoice,
  onError,
  onSuccess,
}: {
  readonly invoice: BaseInvoice;
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
  const colors = hovered && next ? HOVER_COLORS : STATUS_COLORS[invoice.status];

  return (
    <>
      <button
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium w-[100px] justify-center transition-colors whitespace-nowrap',
          next ? 'cursor-pointer' : 'cursor-default',
          colors,
        )}
        onMouseEnter={() => next && setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => next && setConfirming(true)}
        disabled={!next || transitionMutation.isPending}
      >
        {label}
      </button>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change invoice status?</AlertDialogTitle>
            <AlertDialogDescription>
              Move &quot;{invoice.milestone}&quot; ({formatCurrency(invoice.amount)})
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

// -- RevertButton with confirmation --

export function RevertButton({
  invoice,
  onSuccess,
}: {
  readonly invoice: BaseInvoice;
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

// -- DeleteButton with confirmation --

export function DeleteButton({
  invoice,
  projectId,
  onSuccess,
}: {
  readonly invoice: BaseInvoice;
  readonly projectId: string;
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
            ({formatCurrency(invoice.amount)}). This action cannot be undone.
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

// -- Shared field save helper --

export function useInvoiceFieldSave(
  projectId: string,
  invoiceId: string,
  onSuccess?: () => void,
): (field: string, value: string) => void {
  const updateMutation = useUpdateInvoice(projectId);
  return (field: string, value: string) => {
    const data: Record<string, unknown> = {};
    if (field === 'code') data.code = value || null;
    else if (field === 'amount') data.amount = parseFloat(value) || 0;
    else data[field] = value;
    updateMutation.mutate({ invoiceId, data }, { onSuccess });
  };
}
