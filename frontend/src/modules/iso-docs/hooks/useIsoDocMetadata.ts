import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocsApi } from '../services/isoDocs';
import type { MetadataUpdate } from '../types/isoDocs';

export function useIsoDocMetadata(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.metadata(nodeId ?? ''),
    queryFn: () => isoDocsApi.getMetadata(nodeId!),
    enabled: !!nodeId,
    retry: false,
  });
}

export function useUpdateIsoDocMetadata(nodeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: MetadataUpdate) => isoDocsApi.updateMetadata(nodeId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.isoDocs.metadata(nodeId),
      });
    },
  });
}

export function useMetadataSearch(params: {
  standard?: string;
  category?: string;
  clause?: string;
  status?: string;
}) {
  return useQuery({
    queryKey: queryKeys.isoDocs.metadataSearch(params),
    queryFn: () => isoDocsApi.searchMetadata(params),
  });
}

export function useTextSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.isoDocs.textSearch(query),
    queryFn: () => isoDocsApi.searchPages(query),
    enabled: query.length >= 2,
    placeholderData: keepPreviousData,
  });
}
