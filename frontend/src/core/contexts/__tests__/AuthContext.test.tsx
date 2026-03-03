/**
 * Tests for AuthContext authentication state management
 *
 * JWT is now stored in httpOnly cookies (set by the backend).
 * Only user info is cached in localStorage.
 *
 * HTTP calls are intercepted by MSW (set up globally in test/setup.ts).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { AuthProvider } from '../AuthContext';
import { useAuth } from '../../hooks/useAuth';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

const API_URL = 'http://localhost:8000';

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('Initialization', () => {
    it('validates session via cookie when cached user exists', async () => {
      localStorage.setItem('auth_user', JSON.stringify(fixtures.authUser));

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(fixtures.authUser);
      expect(localStorage.getItem('auth_user')).toBe(
        JSON.stringify(fixtures.authUser),
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
    });

    it('clears auth state when session cookie is invalid', async () => {
      localStorage.setItem('auth_user', JSON.stringify(fixtures.authUser));

      server.use(
        http.get(`${API_URL}/api/auth/me`, () => {
          return HttpResponse.json(
            { detail: 'Unauthorized' },
            { status: 401 },
          );
        }),
      );

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
      expect(result.current.user).toEqual(fixtures.authUser);
      expect(localStorage.getItem('auth_user')).toBe(
        JSON.stringify(fixtures.authUser),
      );
    });

    it('throws error when login fails', async () => {
      server.use(
        http.post(`${API_URL}/api/auth/google`, () => {
          return HttpResponse.json(
            { detail: 'Unauthorized domain' },
            { status: 403 },
          );
        }),
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login('invalid-credential');
        }),
      ).rejects.toThrow('Unauthorized domain');

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('Logout', () => {
    it('calls logout endpoint and clears user from localStorage', async () => {
      localStorage.setItem('auth_user', JSON.stringify(fixtures.authUser));

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
    });

    it('updates state to unauthenticated after logout', async () => {
      localStorage.setItem('auth_user', JSON.stringify(fixtures.authUser));

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
      localStorage.setItem('auth_user', JSON.stringify(fixtures.authUser));

      server.use(
        http.get(`${API_URL}/api/auth/me`, () => {
          return HttpResponse.error();
        }),
      );

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
