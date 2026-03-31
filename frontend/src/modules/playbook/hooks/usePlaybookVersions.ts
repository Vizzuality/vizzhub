import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { playbookApi } from '../services/playbook';

export function usePlaybookVersions(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.playbook.versions(nodeId ?? ''),
    queryFn: () => playbookApi.listVersions(nodeId!),
    enabled: !!nodeId,
    refetchOnWindowFocus: false,
  });
}

export function usePlaybookVersion(nodeId: string | null, version: number | null) {
  return useQuery({
    queryKey: queryKeys.playbook.version(nodeId ?? '', version ?? 0),
    queryFn: () => playbookApi.getVersion(nodeId!, version!),
    enabled: !!nodeId && version !== null,
    refetchOnWindowFocus: false,
  });
}
