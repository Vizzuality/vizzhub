import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocsApi } from '../services/isoDocs';

export function useIsoDocVersions(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.versions(nodeId ?? ''),
    queryFn: () => isoDocsApi.listVersions(nodeId!),
    enabled: !!nodeId,
    refetchOnWindowFocus: false,
  });
}

export function useIsoDocVersion(nodeId: string | null, version: number | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.version(nodeId ?? '', version ?? 0),
    queryFn: () => isoDocsApi.getVersion(nodeId!, version!),
    enabled: !!nodeId && version !== null,
    refetchOnWindowFocus: false,
  });
}
