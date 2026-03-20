import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type {
  Invoice,
  InvoiceCreate,
  InvoiceUpdate,
  InvoiceStatus,
} from '../types/tracker';

export function useInvoices(projectId: string) {
  return useQuery<Invoice[]>({
    queryKey: queryKeys.tracker.invoices.byProject(projectId),
    queryFn: () => trackerApi.listInvoices(projectId),
    enabled: !!projectId,
  });
}

export function useCreateInvoice(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: InvoiceCreate) =>
      trackerApi.createInvoice(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(projectId) });
    },
  });
}

export function useUpdateInvoice(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, data }: { invoiceId: string; data: InvoiceUpdate }) =>
      trackerApi.updateInvoice(projectId, invoiceId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(projectId) });
    },
  });
}

export function useTransitionInvoice(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ invoiceId, status }: { invoiceId: string; status: InvoiceStatus }) =>
      trackerApi.transitionInvoice(projectId, invoiceId, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.tracker.costs.batch([]) });
    },
  });
}

export function useDeleteInvoice(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invoiceId: string) =>
      trackerApi.deleteInvoice(projectId, invoiceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(projectId) });
    },
  });
}
