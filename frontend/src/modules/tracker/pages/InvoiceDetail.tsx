import { useParams, useLocation, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { trackerApi } from '../services/tracker';
import InvoiceDetailContent from '../components/InvoiceDetailContent';

export default function InvoiceDetail(): JSX.Element {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const isAdminRoute = location.pathname.startsWith('/admin');

  const { data: invoice, isLoading } = useQuery({
    queryKey: queryKeys.tracker.invoices.detail(invoiceId!),
    queryFn: () => trackerApi.getAdminInvoice(invoiceId!),
    enabled: !!invoiceId,
  });

  if (isLoading || !invoice) return <LoadingSpinner />;

  const backTo = isAdminRoute
    ? '/admin/tracker/invoices'
    : `/tracker/projects/${invoice.project_id}`;

  return (
    <div className="space-y-4 max-w-2xl">
      <Link to={backTo}>
        <Button variant="ghost" size="sm" className="gap-2 -ml-2 h-8">
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
      </Link>
      <InvoiceDetailContent
        invoice={invoice}
        projectId={invoice.project_id}
        currency={invoice.currency}
        projectName={invoice.project_name}
        onDeleted={() => navigate(backTo)}
      />
    </div>
  );
}
