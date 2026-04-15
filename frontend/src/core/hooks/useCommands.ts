import { useMutation, useQuery, useQueryClient, type UseMutationResult } from '@tanstack/react-query';
import {
  commandsApi,
  type ApproveResponse,
  type Command,
  type CommandListParams,
} from '../services/commands';
import { queryKeys } from './queryKeys';

export function useCommands(params: CommandListParams = {}): ReturnType<
  typeof useQuery<Command[]>
> {
  return useQuery({
    queryKey: queryKeys.commands.list(params),
    queryFn: () => commandsApi.list(params),
  });
}

export function useApproveCommand(): UseMutationResult<ApproveResponse, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commandId: string) => commandsApi.approve(commandId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.all });
    },
  });
}

export function useRejectCommand(): UseMutationResult<{ status: 'rejected' }, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commandId: string) => commandsApi.reject(commandId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commands.all });
    },
  });
}
