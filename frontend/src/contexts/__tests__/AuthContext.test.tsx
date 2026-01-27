/**
 * Tests for AuthContext authentication state management
 *
 * This module tests the AuthContext which manages authentication state,
 * token storage, and user session management for the application.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../AuthContext';
import { useAuth } from '../../hooks/useAuth';
import type { User } from '../../types/auth';

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('Initialization', () => {
    it('initializes from localStorage with valid token and user', async () => {
      const mockUser: User = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
      };

      localStorage.setItem('auth_token', 'valid-jwt-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(mockUser);
    });

    it('initializes with empty state when no token in localStorage', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe('Logout', () => {
    it('clears token and user from localStorage', async () => {
      const mockUser: User = {
        id: 'user-456',
        email: 'logout@example.com',
      };

      localStorage.setItem('auth_token', 'token-to-clear');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.logout();

      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('auth_user')).toBeNull();
    });

    it('updates state to unauthenticated after logout', async () => {
      const mockUser: User = {
        id: 'user-789',
        email: 'state@example.com',
      };

      localStorage.setItem('auth_token', 'active-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      result.current.logout();

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Token Management', () => {
    it('stores token in localStorage when setToken is called', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.setToken('new-jwt-token');

      expect(localStorage.getItem('auth_token')).toBe('new-jwt-token');
    });

    it('retrieves token from localStorage when getToken is called', async () => {
      localStorage.setItem('auth_token', 'stored-token-value');

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const token = result.current.getToken();

      expect(token).toBe('stored-token-value');
    });
  });

  describe('Error Handling', () => {
    it('handles corrupted user JSON in localStorage gracefully', async () => {
      localStorage.setItem('auth_token', 'valid-token');
      localStorage.setItem('auth_user', 'invalid-json{{{');

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should not break app - should clear auth state
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to parse stored user data:',
        expect.any(Error)
      );

      // Should clear corrupted data
      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('auth_user')).toBeNull();

      consoleErrorSpy.mockRestore();
    });

    it('throws error when useAuth is used outside AuthProvider', () => {
      // Render hook without wrapper (outside provider)
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within an AuthProvider');
    });
  });
});
