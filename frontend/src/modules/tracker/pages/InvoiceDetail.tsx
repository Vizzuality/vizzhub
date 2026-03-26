import { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Trash2 } from 'lucide-react';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
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
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { trackerApi } from '../services/tracker';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import {
  EditableCell,
  StatusCell,
  PostponeButton,
  PostponementItem,
  RevertButton,
  DeleteButton,
  useInvoiceFieldSave,
  getDisplayDate,
  STATUS_LABELS,
  STATUS_DOT_COLORS,
} from '../components/invoice-shared';
import type { Postponement } from '../types/tracker';

export default function InvoiceDetail(): JSX.Element {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const qc = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.tracker.invoices.detail(invoiceId!),
    queryFn: () => trackerApi.getAdminInvoice(invoiceId!),
    enabled: !!invoiceId,
  });

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.detail(invoiceId!) });
    qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] });
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.totals });
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.postponements(invoice?.project_id ?? '', invoiceId!) });
  }, [qc, invoiceId, invoice?.project_id]);

  const { data: postponements } = useQuery({
    queryKey: queryKeys.tracker.invoices.postponements(invoice?.project_id ?? '', invoiceId!),
    queryFn: () => trackerApi.listPostponements(invoice!.project_id, invoiceId!),
    enabled: !!invoice && invoice.postpone_count > 0,
  });

  const handleDeletePostponement = async (): Promise<void> => {
    if (!invoice) return;
    setDeleting(true);
    try {
      await trackerApi.deleteLatestPostponement(invoice.project_id, invoiceId!);
      invalidate();
    } finally {
      setDeleting(false);
    }
  };

  const save = useInvoiceFieldSave(
    invoice?.project_id ?? '',
    invoiceId ?? '',
    invalidate,
  );

  const showError = useCallback((msg: string) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(null), 5000);
  }, []);

  if (isLoading || !invoice) return <LoadingSpinner />;

  const displayDate = getDisplayDate(invoice);

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center gap-3">
        <Link to="/admin/tracker/invoices">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <h2 className="text-lg font-semibold flex-1">{invoice.milestone}</h2>
        <DeleteButton
          invoice={invoice}
          projectId={invoice.project_id}
          currency={invoice.currency}
          label="Delete"
          onSuccess={invalidate}
        />
      </div>

      {errorMsg && (
        <div className="px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
          {errorMsg}
        </div>
      )}

      <Card>
        <CardContent className="pt-5 space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground text-xs">Project</span>
              <div>
                <Link
                  to={`/tracker/projects/${invoice.project_id}`}
                  className="hover:underline font-medium"
                >
                  {invoice.project_name}
                </Link>
              </div>
            </div>

            <div>
              <span className="text-muted-foreground text-xs">Status</span>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${STATUS_DOT_COLORS[invoice.status]}`} />
                <span>{STATUS_LABELS[invoice.status]}</span>
              </div>
            </div>

            <div>
              <span className="text-muted-foreground text-xs">Amount</span>
              <div>
                <EditableCell
                  value={invoice.amount.toString()}
                  display={formatCurrency(invoice.amount, invoice.currency, 2)}
                  inputType="number"
                  onSave={(v) => save('amount', v)}
                  inputClass="h-6 w-32 text-sm px-1"
                />
              </div>
            </div>

            <div>
              <span className="text-muted-foreground text-xs">Due date</span>
              <div>
                <EditableCell
                  value={displayDate}
                  inputType="date"
                  onSave={(v) => save('due_date', v)}
                  inputClass="h-6 w-36 text-sm px-1"
                />
              </div>
            </div>

            <div>
              <span className="text-muted-foreground text-xs">Code</span>
              <div>
                <EditableCell
                  value={invoice.code ?? ''}
                  placeholder="add code"
                  onSave={(v) => save('code', v)}
                  inputClass="h-6 w-32 text-sm px-1"
                />
              </div>
            </div>

            <div>
              <span className="text-muted-foreground text-xs">Milestone</span>
              <div>
                <EditableCell
                  value={invoice.milestone}
                  onSave={(v) => save('milestone', v)}
                  inputClass="h-6 w-full text-sm px-1"
                />
              </div>
            </div>

            {invoice.invoiced_on && (
              <div>
                <span className="text-muted-foreground text-xs">Invoiced on</span>
                <div className="tabular-nums">{invoice.invoiced_on}</div>
              </div>
            )}

            {invoice.observations && (
              <div className="col-span-2">
                <span className="text-muted-foreground text-xs">Observations</span>
                <div>{invoice.observations}</div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-2 border-t">
            <StatusCell
              invoice={invoice}
              currency={invoice.currency}
              onError={showError}
              onSuccess={invalidate}
            />
            <PostponeButton
              invoice={invoice}
              currency={invoice.currency}
              onError={showError}
              onSuccess={invalidate}
            />
            <div className="ml-auto">
              <RevertButton invoice={invoice} onSuccess={invalidate} />
            </div>
          </div>

          {postponements && postponements.length > 0 && (
            <div className="border-t pt-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Postponement history
                </span>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      className="text-muted-foreground hover:text-destructive transition-colors p-0.5 disabled:opacity-50"
                      title="Remove last postponement"
                      disabled={deleting}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Remove last postponement?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will remove the most recent postponement
                        (date: {postponements[0].postponed_to}). The invoice will revert
                        to its previous postponement date or original due date.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={handleDeletePostponement}
                        disabled={deleting}
                      >
                        Remove
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
              <div className="space-y-2">
                {postponements.map((p: Postponement) => (
                  <PostponementItem key={p.id} postponement={p} />
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
