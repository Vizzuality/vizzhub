/**
 * Tests for AuthContext authentication state management
 *
 * This module tests the AuthContext which manages authentication state,
 * token storage, and user session management via Google OAuth.
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';
import { AuthProvider } from '../AuthContext';
import { useAuth } from '../../hooks/useAuth';
import type { UserPublic } from '../../types/auth';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

const mockUser: UserPublic = {
  id: 'user-123',
  email: 'test@vizzuality.com',
  first_name: 'Test',
  last_name: 'User',
  picture: 'https://example.com/photo.jpg',
  role: 'user',
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initialization', () => {
    it('initializes from localStorage with valid token after API validation', async () => {
      localStorage.setItem('auth_token', 'valid-jwt-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      // Mock successful token validation
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(mockUser);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/me'),
        expect.objectContaining({
          headers: { Authorization: 'Bearer valid-jwt-token' },
        })
      );
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
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('clears auth state when stored token is invalid', async () => {
      localStorage.setItem('auth_token', 'invalid-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      // Mock failed token validation
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(localStorage.getItem('auth_token')).toBeNull();
    });
  });

  describe('Login', () => {
    it('authenticates with Google credential and stores token', async () => {
      const authResponse = {
        access_token: 'new-jwt-token',
        token_type: 'bearer',
        user: mockUser,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => authResponse,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login('google-credential-token');
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(mockUser);
      expect(localStorage.getItem('auth_token')).toBe('new-jwt-token');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/google'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ credential: 'google-credential-token' }),
        })
      );
    });

    it('throws error when login fails', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Unauthorized domain' }),
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login('invalid-credential');
        })
      ).rejects.toThrow('Unauthorized domain');

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('Logout', () => {
    it('clears token and user from localStorage', async () => {
      localStorage.setItem('auth_token', 'token-to-clear');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      // Mock successful validation first
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      act(() => {
        result.current.logout();
      });

      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('auth_user')).toBeNull();
    });

    it('updates state to unauthenticated after logout', async () => {
      localStorage.setItem('auth_token', 'active-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Token Management', () => {
    it('retrieves token from localStorage when getToken is called', async () => {
      localStorage.setItem('auth_token', 'stored-token-value');

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const token = result.current.getToken();

      expect(token).toBe('stored-token-value');
    });

    it('returns null when no token is stored', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const token = result.current.getToken();

      expect(token).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('handles network errors during token validation gracefully', async () => {
      localStorage.setItem('auth_token', 'valid-token');
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      // Mock network error
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should clear auth state on validation failure
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });

    it('throws error when useAuth is used outside AuthProvider', () => {
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within an AuthProvider');
    });
  });
});
