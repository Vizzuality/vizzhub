/**
 * Hooks for user management (admin only)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/core/services/client';
import { User, UserRole } from '../types/auth';
import { queryKeys } from './queryKeys';

/**
 * Fetch all users (admin only)
 */
export function useUsers(): ReturnType<typeof useQuery<User[], Error>> {
  return useQuery({
    queryKey: queryKeys.users.all,
    queryFn: async (): Promise<User[]> => {
      const response = await api.get<User[]>('/admin/users');
      return response.data;
    },
  });
}

/**
 * Update user role (admin only)
 */
export function useUpdateUserRole(): ReturnType<
  typeof useMutation<User, Error, { userId: string; role: UserRole }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, role }): Promise<User> => {
      const response = await api.patch<User>(`/admin/users/${userId}`, { role });
      return response.data;
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

/**
 * Delete user (admin only)
 */
export function useDeleteUser(): ReturnType<typeof useMutation<void, Error, string>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId): Promise<void> => {
      await api.delete(`/admin/users/${userId}`);
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}
