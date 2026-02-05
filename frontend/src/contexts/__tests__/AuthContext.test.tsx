/**
 * Tests for AuthContext authentication state management
 *
 * JWT is now stored in httpOnly cookies (set by the backend).
 * Only user info is cached in localStorage.
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
    it('validates session via cookie when cached user exists', async () => {
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

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
          credentials: 'include',
        })
      );
    });

    it('initializes with empty state when no cached user', async () => {
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

    it('clears auth state when session cookie is invalid', async () => {
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

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
      expect(localStorage.getItem('auth_user')).toBeNull();
    });
  });

  describe('Login', () => {
    it('authenticates with Google credential and stores user info', async () => {
      const authResponse = {
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
      expect(localStorage.getItem('auth_user')).toBe(JSON.stringify(mockUser));
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/google'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
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
    it('calls logout endpoint and clears user from localStorage', async () => {
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      // First call: session validation
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      // Second call: logout endpoint
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Logged out successfully' }),
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(localStorage.getItem('auth_user')).toBeNull();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/logout'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      );
    });

    it('updates state to unauthenticated after logout', async () => {
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Logged out successfully' }),
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('handles network errors during session validation gracefully', async () => {
      localStorage.setItem('auth_user', JSON.stringify(mockUser));

      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

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
