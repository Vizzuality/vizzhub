/**
 * Hooks for user management (admin only)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/core/services/client';
import { User, UserRole, FunctionalArea, Rate } from '../types/auth';
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
 * Fetch a single user by ID (admin only).
 */
export function useUser(
  userId: string,
): ReturnType<typeof useQuery<User, Error>> {
  return useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: async (): Promise<User> => {
      const response = await api.get<User>(`/admin/users/${userId}`);
      return response.data;
    },
    enabled: !!userId,
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
 * Update user fields (admin only)
 */
export function useUpdateUser(): ReturnType<
  typeof useMutation<User, Error, { userId: string; data: Record<string, unknown> }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, data }): Promise<User> => {
      const response = await api.patch<User>(`/admin/users/${userId}`, data);
      return response.data;
    },
    onSuccess: (_data, { userId }): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(userId) });
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
    onSuccess: (_data, { userId }): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(userId) });
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

/**
 * Sync a user's Slack profile by email lookup (admin only).
 */
export function useSyncSlack(): ReturnType<
  typeof useMutation<User, Error, string>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId): Promise<User> => {
      const response = await api.post<User>(`/admin/users/${userId}/sync-slack`);
      return response.data;
    },
    onSuccess: (_data, userId): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(userId) });
    },
  });
}

/**
 * Sync Slack profiles for all active users (admin only).
 */
export function useSyncSlackAll(): ReturnType<
  typeof useMutation<User[], Error, void>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (): Promise<User[]> => {
      const response = await api.post<User[]>('/admin/users/sync-slack-all');
      return response.data;
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

/**
 * Fetch functional areas.
 */
export function useFunctionalAreas(): ReturnType<typeof useQuery<FunctionalArea[], Error>> {
  return useQuery({
    queryKey: queryKeys.functionalAreas.all,
    queryFn: async (): Promise<FunctionalArea[]> => {
      const response = await api.get<FunctionalArea[]>('/functional-areas');
      return response.data;
    },
  });
}

/**
 * Fetch rates.
 */
export function useRates(): ReturnType<typeof useQuery<Rate[], Error>> {
  return useQuery({
    queryKey: ['rates'],
    queryFn: async (): Promise<Rate[]> => {
      const response = await api.get<Rate[]>('/rates');
      return response.data;
    },
  });
}
