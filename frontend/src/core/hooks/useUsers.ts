/**
 * Hooks for user management (admin only)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/core/services/client';
import { User, UserRole } from '../types/auth';
import { queryKeys } from './queryKeys';

/**
 * Fetch users (admin only). Excludes inactive by default.
 */
export function useUsers(
  includeInactive = false,
): ReturnType<typeof useQuery<User[], Error>> {
  return useQuery({
    queryKey: [...queryKeys.users.all, { includeInactive }],
    queryFn: async (): Promise<User[]> => {
      const params = includeInactive ? { include_inactive: true } : {};
      const response = await api.get<User[]>('/admin/users', { params });
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
 * Toggle user active status (admin only)
 */
export function useToggleUserActive(): ReturnType<
  typeof useMutation<User, Error, { userId: string; active: boolean }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, active }): Promise<User> => {
      const response = await api.patch<User>(`/admin/users/${userId}`, { active });
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
