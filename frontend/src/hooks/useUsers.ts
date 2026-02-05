/**
 * Hooks for user management (admin only)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { User, UserRole } from '../types/auth';
import { queryKeys } from './queryKeys';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers, credentials: 'include' });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }

  return response;
}

/**
 * Fetch all users (admin only)
 */
export function useUsers(): ReturnType<typeof useQuery<User[], Error>> {
  return useQuery({
    queryKey: queryKeys.users.all,
    queryFn: async (): Promise<User[]> => {
      const response = await fetchWithAuth(`${API_URL}/api/admin/users`);
      return response.json();
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
      const response = await fetchWithAuth(`${API_URL}/api/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      return response.json();
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
      await fetchWithAuth(`${API_URL}/api/admin/users/${userId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}
