import { useState } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useInvoices,
  useCreateInvoice,
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
  waiting_for_payment: 'bg-aux-cool-steel/20 text-aux-cool-steel',
  paid: 'bg-aux-neon-grass/20 text-aux-neon-grass',
};

const ALLOWED_TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  scheduled: ['pending_to_issue'],
  pending_to_issue: ['waiting_for_payment', 'scheduled'],
  waiting_for_payment: ['paid', 'pending_to_issue'],
  paid: ['waiting_for_payment'],
};

function InvoiceRow({
  invoice,
  projectId,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
}): JSX.Element {
  const transitionMutation = useTransitionInvoice(projectId);
  const deleteMutation = useDeleteInvoice(projectId);
  const transitions = ALLOWED_TRANSITIONS[invoice.status];

  return (
    <tr className="group/row border-b last:border-0">
      <td className="py-2 text-sm">{invoice.milestone}</td>
      <td className="py-2 text-sm text-muted-foreground">{invoice.code ?? '—'}</td>
      <td className="py-2 text-sm text-right tabular-nums">
        {formatCurrency(invoice.amount)}
      </td>
      <td className="py-2 text-sm">{invoice.due_date}</td>
      <td className="py-2">
        <select
          className={cn(
            'appearance-none cursor-pointer border-0 rounded px-2 py-0.5 text-xs font-medium',
            STATUS_COLORS[invoice.status],
          )}
          value={invoice.status}
          onChange={(e) => {
            const newStatus = e.target.value as InvoiceStatus;
            if (newStatus !== invoice.status) {
              transitionMutation.mutate({ invoiceId: invoice.id, status: newStatus });
            }
          }}
          disabled={transitionMutation.isPending}
        >
          <option value={invoice.status}>{STATUS_LABELS[invoice.status]}</option>
          {transitions.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </td>
      <td className="py-2 text-right">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 opacity-0 group-hover/row:opacity-100 text-destructive"
          onClick={() => deleteMutation.mutate(invoice.id)}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
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

  const totalAmount = (invoices ?? []).reduce((s, i) => s + i.amount, 0);
  const paidAmount = (invoices ?? []).filter((i) => i.status === 'paid').reduce((s, i) => s + i.amount, 0);

  const handleAdd = (): void => {
    const amount = parseFloat(newAmount);
    if (!newCode || !newMilestone || isNaN(amount) || !newDueDate) return;
    createMutation.mutate(
      { code: newCode, milestone: newMilestone, amount, due_date: newDueDate },
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
    <Card>
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

        {invoices && invoices.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="text-left font-medium pb-1">Milestone</th>
                  <th className="text-left font-medium pb-1">Code</th>
                  <th className="text-right font-medium pb-1">Amount</th>
                  <th className="text-left font-medium pb-1">Due</th>
                  <th className="text-left font-medium pb-1">Status</th>
                  <th className="w-32" />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <InvoiceRow key={inv.id} invoice={inv} projectId={projectId} />
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
              className="h-8 text-sm flex-1 min-w-[120px]"
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
