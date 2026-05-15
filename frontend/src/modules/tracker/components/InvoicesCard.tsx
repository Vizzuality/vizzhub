import { useState, Fragment, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Plus, ExternalLink } from 'lucide-react';
import { useInvoices, useCreateInvoice } from '../hooks/useInvoices';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import {
  EditableCell,
  StatusCell,
  PostponeButton,
  PostponementHistory,
  HistoryToggle,
  RevertButton,
  DeleteButton,
  useInvoiceFieldSave,
  getDisplayDate,
} from './invoice-shared';
import type { Invoice } from '../types/tracker';

interface InvoicesCardProps {
  readonly projectId: string;
  readonly currency: string;
}

const COL_COUNT = 6;

function InvoiceRow({
  invoice,
  projectId,
  currency,
  onError,
}: {
  readonly invoice: Invoice;
  readonly projectId: string;
  readonly currency: string;
  readonly onError: (msg: string) => void;
}): JSX.Element {
  const qc = useQueryClient();
  const [historyOpen, setHistoryOpen] = useState(false);
  const invalidate = useCallback(
    () => { qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(projectId) }); },
    [qc, projectId],
  );
  const save = useInvoiceFieldSave(projectId, invoice.id, invalidate);

  const displayDate = getDisplayDate(invoice);

  return (
    <Fragment>
      <tr className="border-b last:border-0">
        <td className="py-2 text-sm">
          <EditableCell
            value={invoice.milestone}
            display={invoice.milestone}
            displayClass="truncate block max-w-[200px]"
            onSave={(v) => save('milestone', v)}
            inputClass="h-6 w-full text-sm px-1"
          />
        </td>
        <td className="py-2 text-sm hidden lg:table-cell">
          <EditableCell
            value={invoice.code ?? ''}
            placeholder="add code"
            onSave={(v) => save('code', v)}
            inputClass="h-6 w-24 text-sm px-1"
          />
        </td>
        <td className="py-2 text-sm text-right tabular-nums pr-4">
          <EditableCell
            value={invoice.amount.toString()}
            display={formatCurrency(invoice.amount, currency, 2)}
            inputType="number"
            onSave={(v) => save('amount', v)}
            inputClass="h-6 w-24 text-sm px-1 text-right"
          />
        </td>
        <td className="py-2 text-sm pl-4 hidden sm:table-cell">
          <EditableCell
            value={displayDate}
            inputType="date"
            onSave={(v) => save('due_date', v)}
            inputClass="h-6 w-36 text-sm px-1"
          />
        </td>
        <td className="py-2">
          <div className="flex items-center gap-2">
            <StatusCell invoice={invoice} currency={currency} onError={onError} onSuccess={invalidate} />
            <PostponeButton invoice={invoice} currency={currency} onError={onError} onSuccess={invalidate} />
            <HistoryToggle
              count={invoice.postpone_count}
              expanded={historyOpen}
              onToggle={() => setHistoryOpen(!historyOpen)}
            />
          </div>
        </td>
        <td className="py-2 text-right hidden sm:table-cell">
          <div className="flex items-center gap-1 justify-end">
            <Link to={`/tracker/invoices/${invoice.id}`}>
              <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground">
                <ExternalLink className="h-3 w-3" />
              </Button>
            </Link>
            <RevertButton invoice={invoice} onSuccess={invalidate} />
            <DeleteButton invoice={invoice} projectId={projectId} currency={currency} onSuccess={invalidate} />
          </div>
        </td>
      </tr>
      <PostponementHistory
        projectId={projectId}
        invoiceId={invoice.id}
        expanded={historyOpen}
        colSpan={COL_COUNT}
        onDelete={invalidate}
      />
    </Fragment>
  );
}

export default function InvoicesCard({ projectId, currency }: InvoicesCardProps): JSX.Element {
  const { data: invoices } = useInvoices(projectId);
  const createMutation = useCreateInvoice(projectId);
  const [adding, setAdding] = useState(false);
  const [newCode, setNewCode] = useState('');
  const [newMilestone, setNewMilestone] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const totalAmount = (invoices ?? []).reduce((s, i) => s + Number(i.amount ?? 0), 0);
  const paidAmount = (invoices ?? [])
    .filter((i) => i.status === 'paid')
    .reduce((s, i) => s + Number(i.amount ?? 0), 0);

  const showError = (msg: string): void => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 5000);
  };

  const handleAdd = (): void => {
    const amount = Number.parseFloat(newAmount);
    if (!newMilestone || Number.isNaN(amount) || !newDueDate) return;
    createMutation.mutate(
      { code: newCode || undefined, milestone: newMilestone, amount, due_date: newDueDate },
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
              {formatCurrency(paidAmount, currency, 2)} / {formatCurrency(totalAmount, currency, 2)}
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
                  <th className="text-left font-medium pb-1">Milestone</th>
                  <th className="text-left font-medium pb-1 hidden lg:table-cell">Code</th>
                  <th className="text-right font-medium pb-1 pr-4">Amount</th>
                  <th className="text-left font-medium pb-1 pl-4 hidden sm:table-cell">Due</th>
                  <th className="text-left font-medium pb-1">Status</th>
                  <th className="w-24 hidden sm:table-cell" />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <InvoiceRow key={inv.id} invoice={inv} projectId={projectId} currency={currency} onError={showError} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {invoices?.length === 0 && !adding && (
          <p className="text-muted-foreground text-sm">No invoices</p>
        )}

        {adding ? (
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <Input placeholder="Code" value={newCode} onChange={(e) => setNewCode(e.target.value)} className="w-24 h-8 text-sm" />
            <Input placeholder="Milestone" value={newMilestone} onChange={(e) => setNewMilestone(e.target.value)} className="h-8 text-sm min-w-[120px] flex-1" />
            <Input type="number" min="0" step="0.01" placeholder="Amount" value={newAmount} onChange={(e) => setNewAmount(e.target.value)} className="w-28 h-8 text-right text-sm" />
            <Input type="date" value={newDueDate} onChange={(e) => setNewDueDate(e.target.value)} className="w-36 h-8 text-sm" />
            <Button size="sm" className="h-8" onClick={handleAdd} disabled={createMutation.isPending}>Save</Button>
            <Button variant="ghost" size="sm" className="h-8" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        ) : (
          <Button variant="ghost" size="sm" className="mt-3 gap-1 text-muted-foreground" onClick={() => setAdding(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add invoice
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
