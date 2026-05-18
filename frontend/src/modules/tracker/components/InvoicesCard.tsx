import { useState } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Can, Action } from '@/core/permissions';
import { useInvoices } from '../hooks/useInvoices';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import {
  STATUS_LABELS,
  STATUS_DOT_COLORS,
  getDisplayDate,
} from './invoice-shared';
import InvoiceOverlay from './InvoiceOverlay';
import type { Invoice } from '../types/tracker';

interface InvoicesCardProps {
  readonly projectId: string;
  readonly currency: string;
  readonly projectName?: string;
}

function InvoiceRow({
  invoice,
  currency,
  onClick,
}: {
  readonly invoice: Invoice;
  readonly currency: string;
  readonly onClick: () => void;
}): JSX.Element {
  const displayDate = getDisplayDate(invoice);
  return (
    <tr
      className="border-b last:border-0 hover:bg-muted/40 cursor-pointer"
      onClick={onClick}
    >
      <td className="py-2 text-sm">
        <span className="truncate block max-w-[200px]">{invoice.milestone}</span>
      </td>
      <td className="py-2 text-sm hidden lg:table-cell">{invoice.code ?? '—'}</td>
      <td className="py-2 text-sm text-right tabular-nums pr-4">
        {formatCurrency(invoice.amount, currency, 2)}
      </td>
      <td className="py-2 text-sm pl-4 hidden sm:table-cell tabular-nums">{displayDate}</td>
      <td className="py-2">
        <div className="inline-flex items-center gap-1.5">
          <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', STATUS_DOT_COLORS[invoice.status])} />
          <span className="text-sm">{STATUS_LABELS[invoice.status]}</span>
          {invoice.postpone_count > 0 && (
            <span className="text-xs text-muted-foreground ml-1">×{invoice.postpone_count}</span>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function InvoicesCard({
  projectId,
  currency,
  projectName,
}: InvoicesCardProps): JSX.Element {
  const { data: invoices } = useInvoices(projectId);
  const [overlay, setOverlay] = useState<{ mode: 'edit' | 'create'; invoiceId?: string } | null>(null);

  const totalAmount = (invoices ?? []).reduce((s, i) => s + Number(i.amount ?? 0), 0);
  const paidAmount = (invoices ?? [])
    .filter((i) => i.status === 'paid')
    .reduce((s, i) => s + Number(i.amount ?? 0), 0);

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
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <InvoiceRow
                    key={inv.id}
                    invoice={inv}
                    currency={currency}
                    onClick={() => setOverlay({ mode: 'edit', invoiceId: inv.id })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {invoices?.length === 0 && (
          <p className="text-muted-foreground text-sm">No invoices</p>
        )}

        <Can do={Action.TRACKER_MANAGE}>
          <Button
            variant="ghost"
            size="sm"
            className="mt-3 gap-1 text-muted-foreground"
            onClick={() => setOverlay({ mode: 'create' })}
          >
            <Plus className="h-3.5 w-3.5" />
            Add invoice
          </Button>
        </Can>

        <InvoiceOverlay
          open={!!overlay}
          onOpenChange={(open) => { if (!open) setOverlay(null); }}
          mode={overlay?.mode ?? 'edit'}
          projectId={projectId}
          currency={currency}
          projectName={projectName}
          invoiceId={overlay?.invoiceId}
        />
      </CardContent>
    </Card>
  );
}
