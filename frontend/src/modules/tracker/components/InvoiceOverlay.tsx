import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Sheet, SheetContent } from '@/shared/components/ui/sheet';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import InvoiceDetailContent from './InvoiceDetailContent';

interface InvoiceOverlayProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly mode: 'edit' | 'create';
  readonly projectId: string;
  readonly currency: string;
  readonly projectName?: string;
  readonly invoiceId?: string;
}

export default function InvoiceOverlay({
  open,
  onOpenChange,
  mode,
  projectId,
  currency,
  projectName,
  invoiceId,
}: InvoiceOverlayProps): JSX.Element {
  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.tracker.invoices.detail(invoiceId ?? ''),
    queryFn: () => trackerApi.getAdminInvoice(invoiceId!),
    enabled: open && mode === 'edit' && !!invoiceId,
  });

  const close = (): void => onOpenChange(false);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto">
        {mode === 'edit' && (isLoading || !invoice) ? (
          <LoadingSpinner />
        ) : (
          <div className="space-y-3">
            {mode === 'edit' && invoiceId && (
              <Link
                to={`/tracker/invoices/${invoiceId}`}
                className="inline-flex items-center"
                onClick={close}
              >
                <Button variant="ghost" size="sm" className="gap-2 -ml-2 h-7 text-xs text-muted-foreground">
                  <ExternalLink className="w-3 h-3" />
                  Open full page
                </Button>
              </Link>
            )}
            <InvoiceDetailContent
              invoice={mode === 'edit' ? invoice : undefined}
              projectId={projectId}
              currency={currency}
              projectName={projectName}
              onClose={close}
              onCreated={close}
              onDeleted={close}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
