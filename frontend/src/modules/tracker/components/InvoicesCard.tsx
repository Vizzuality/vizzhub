import { useState } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
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
import { Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useInvoices,
  useCreateInvoice,
  useUpdateInvoice,
  useTransitionInvoice,
  useDeleteInvoice,
} from '../hooks/useInvoices';
import { formatCurrency } from '../utils/constants';
import type { Invoice, InvoiceStatus } from '../types/tracker';

interface InvoicesCardProps {
  readonly projectId: string;
}

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending',
  waiting_for_payment: 'Waiting',
  paid: 'Paid',
};

const STATUS_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'bg-aux-dust-grey text-aux-onix',
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

function StatusCell({
  invoice,
  projectId,
  onError,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  const transitionMutation = useTransitionInvoice(projectId);
  const next = NEXT_STATUS[invoice.status];

  const handleTransition = (): void => {
    if (!next) return;
    transitionMutation.mutate(
      { invoiceId: invoice.id, status: next },
      {
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? 'Transition failed';
          onError(msg);
        },
      },
    );
  };

  const label = hovered && next ? NEXT_LABELS[invoice.status] : STATUS_LABELS[invoice.status];
  const colors = hovered && next ? STATUS_COLORS[next] : STATUS_COLORS[invoice.status];

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

function EditableCode({
  invoice,
  projectId,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(invoice.code ?? '');
  const updateMutation = useUpdateInvoice(projectId);

  const handleSave = (): void => {
    const trimmed = value.trim();
    if (trimmed !== (invoice.code ?? '')) {
      updateMutation.mutate(
        { invoiceId: invoice.id, data: { code: trimmed || null } },
        { onSuccess: () => setEditing(false) },
      );
    } else {
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSave();
          if (e.key === 'Escape') setEditing(false);
        }}
        className="h-6 w-24 text-sm px-1"
        autoFocus
      />
    );
  }

  return (
    <span
      className="cursor-pointer hover:underline text-sm"
      onClick={() => { setValue(invoice.code ?? ''); setEditing(true); }}
      title="Click to edit"
    >
      {invoice.code || <span className="text-muted-foreground/50 italic">add code</span>}
    </span>
  );
}

function InvoiceRow({
  invoice,
  projectId,
  onError,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const deleteMutation = useDeleteInvoice(projectId);
  const transitions = ALLOWED_TRANSITIONS[invoice.status];
  const transitionMutation = useTransitionInvoice(projectId);

  return (
    <tr className="border-b last:border-0">
      <td className="py-2">
        <EditableCode invoice={invoice} projectId={projectId} />
      </td>
      <td className="py-2 text-sm">{invoice.milestone}</td>
      <td className="py-2 text-sm text-right tabular-nums pr-4">
        {formatCurrency(invoice.amount)}
      </td>
      <td className="py-2 text-sm pl-4">{invoice.due_date}</td>
      <td className="py-2">
        <StatusCell invoice={invoice} projectId={projectId} onError={onError} />
      </td>
      <td className="py-2 text-right">
        <div className="flex items-center gap-1 justify-end">
          {invoice.status === 'paid' && transitions.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground"
              onClick={() => transitionMutation.mutate({ invoiceId: invoice.id, status: transitions[0] })}
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
                  This will permanently delete the invoice &quot;{invoice.milestone}&quot;
                  ({formatCurrency(invoice.amount)}). This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  onClick={() => deleteMutation.mutate(invoice.id)}
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

export default function InvoicesCard({ projectId }: InvoicesCardProps): JSX.Element {
  const { data: invoices } = useInvoices(projectId);
  const createMutation = useCreateInvoice(projectId);
  const [adding, setAdding] = useState(false);
  const [newCode, setNewCode] = useState('');
  const [newMilestone, setNewMilestone] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const totalAmount = (invoices ?? []).reduce((s, i) => s + i.amount, 0);
  const paidAmount = (invoices ?? []).filter((i) => i.status === 'paid').reduce((s, i) => s + i.amount, 0);

  const showError = (msg: string): void => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 5000);
  };

  const handleAdd = (): void => {
    const amount = parseFloat(newAmount);
    if (!newMilestone || isNaN(amount) || !newDueDate) return;
    createMutation.mutate(
      {
        code: newCode || undefined,
        milestone: newMilestone,
        amount,
        due_date: newDueDate,
      },
      {
        onSuccess: () => {
          setAdding(false);
          setNewCode('');
          setNewMilestone('');
          setNewAmount('');
          setNewDueDate('');
        },
      },
    );
  };

  return (
    <Card className="min-w-0 overflow-hidden">
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Invoices
          </div>
          {invoices && invoices.length > 0 && (
            <div className="text-sm tabular-nums text-muted-foreground">
              {formatCurrency(paidAmount)}
              {' / '}
              {formatCurrency(totalAmount)}
            </div>
          )}
        </div>

        {errorMsg && (
          <div className="mb-3 px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
            {errorMsg}
          </div>
        )}

        {invoices && invoices.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="text-left font-medium pb-1">Code</th>
                  <th className="text-left font-medium pb-1">Milestone</th>
                  <th className="text-right font-medium pb-1 pr-4">Amount</th>
                  <th className="text-left font-medium pb-1 pl-4">Due</th>
                  <th className="text-left font-medium pb-1">Status</th>
                  <th className="w-24" />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <InvoiceRow key={inv.id} invoice={inv} projectId={projectId} onError={showError} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {invoices && invoices.length === 0 && !adding && (
          <p className="text-muted-foreground text-sm">No invoices</p>
        )}

        {adding ? (
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <Input
              placeholder="Code"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              className="w-24 h-8 text-sm"
            />
            <Input
              placeholder="Milestone"
              value={newMilestone}
              onChange={(e) => setNewMilestone(e.target.value)}
              className="h-8 text-sm min-w-[120px] flex-1"
            />
            <Input
              type="number"
              min="0"
              step="0.01"
              placeholder="Amount"
              value={newAmount}
              onChange={(e) => setNewAmount(e.target.value)}
              className="w-28 h-8 text-right text-sm"
            />
            <Input
              type="date"
              value={newDueDate}
              onChange={(e) => setNewDueDate(e.target.value)}
              className="w-36 h-8 text-sm"
            />
            <Button size="sm" className="h-8" onClick={handleAdd} disabled={createMutation.isPending}>
              Save
            </Button>
            <Button variant="ghost" size="sm" className="h-8" onClick={() => setAdding(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="mt-3 gap-1 text-muted-foreground"
            onClick={() => setAdding(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Add invoice
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
