import { useState } from 'react';
import { Input } from '@/shared/components/ui/input';
import { cn } from '@/lib/utils';
import { useUpdateInvoice } from '../hooks/useInvoices';
import type { InvoiceStatus } from '../types/tracker';

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending to invoice',
  postpone_pending: 'Awaiting approval',
  postponed: 'Postponed',
  waiting_for_payment: 'Waiting for payment',
  paid: 'Paid',
};

export const STATUS_DOT_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'bg-muted-foreground',
  pending_to_issue: 'bg-aux-yellow',
  postpone_pending: 'bg-blue-500',
  postponed: 'bg-orange-400',
  waiting_for_payment: 'bg-aux-red',
  paid: 'bg-aux-neon-grass',
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
    <button
      type="button"
      className={cn('cursor-pointer hover:underline bg-transparent border-0 p-0 text-left', displayClass)}
      onClick={startEditing}
      title={display || initial || undefined}
    >
      {display || initial || (
        <span className="text-muted-foreground italic">{placeholder ?? 'edit'}</span>
      )}
    </button>
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
