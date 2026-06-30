import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '../services/portfolio';
import type { ClientCreate, ClientListParams, ClientUpdate, MergeRequest } from '../types/portfolio';

export function useClients(params: ClientListParams = {}) {
  return useQuery({
    queryKey: queryKeys.portfolio.clients.list(params as unknown as Record<string, unknown>),
    queryFn: () => portfolioApi.listClients(params),
  });
}

export function useCreateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClientCreate) => portfolioApi.createClient(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.portfolio.clients.all }),
  });
}

export function useUpdateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClientUpdate }) =>
      portfolioApi.updateClient(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.portfolio.clients.all }),
  });
}

export function useMergeClients() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ targetId, data }: { targetId: string; data: MergeRequest }) =>
      portfolioApi.mergeClients(targetId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.portfolio.clients.all }),
  });
}
