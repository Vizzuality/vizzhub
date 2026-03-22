/**
 * Authentication Context for Google OAuth
 *
 * JWT is stored in an httpOnly cookie (set by the backend).
 * Only user info is cached in localStorage to avoid UI flicker on reload.
 */

import { createContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react';
import { UserPublic, AuthState, AuthContextType, AuthLoginResponse } from '../types/auth';

const USER_STORAGE_KEY = 'auth_user';
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_AUTH_STATE: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
  permissions: [],
};

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [authState, setAuthState] = useState<AuthState>(DEFAULT_AUTH_STATE);
  const [isImpersonating, setIsImpersonating] = useState<boolean>(false);

  /**
   * Login with Google credential.
   * Backend sets the httpOnly cookie; we only store user info locally.
   */
  const login = useCallback(async (credential: string): Promise<void> => {
    const response = await fetch(`${API_URL}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ credential }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Authentication failed');
    }

    const data: AuthLoginResponse = await response.json();

    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user));

    setAuthState({
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
      permissions: data.user.permissions ?? [],
    });
  }, []);

  /**
   * Logout: ask backend to clear the cookie, then clear local user cache.
   */
  const logout = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Best-effort; clear local state regardless
    }

    localStorage.removeItem(USER_STORAGE_KEY);
    setIsImpersonating(false);
    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      permissions: [],
    });
  }, []);

  /**
   * Validate current session by calling /auth/me with the cookie.
   */
  const validateSession = useCallback(async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        const { is_impersonating, ...userData } = data as UserPublic & {
          is_impersonating?: boolean;
        };
        const user: UserPublic = userData;
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
        setIsImpersonating(is_impersonating ?? false);
        setAuthState({
          user,
          isAuthenticated: true,
          isLoading: false,
          permissions: user.permissions ?? [],
        });
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  // On mount: if we have cached user info, try to validate the session cookie
  useEffect(() => {
    const initAuth = async (): Promise<void> => {
      const cachedUser = localStorage.getItem(USER_STORAGE_KEY);

      if (cachedUser) {
        const isValid = await validateSession();
        if (!isValid) {
          localStorage.removeItem(USER_STORAGE_KEY);
          setAuthState({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            permissions: [],
          });
        }
      } else {
        setAuthState((prev) => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, [validateSession]);

  const impersonate = useCallback(async (userId: string): Promise<void> => {
    const response = await fetch(`${API_URL}/api/admin/users/${userId}/impersonate`, {
      method: 'POST',
      credentials: 'include',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Impersonation failed');
    }

    const user: UserPublic = await response.json();
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    setIsImpersonating(true);
    setAuthState({
      user,
      isAuthenticated: true,
      isLoading: false,
      permissions: user.permissions ?? [],
    });
  }, []);

  const stopImpersonating = useCallback(async (): Promise<void> => {
    const response = await fetch(`${API_URL}/api/admin/users/stop-impersonate`, {
      method: 'POST',
      credentials: 'include',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to stop impersonation');
    }

    const user: UserPublic = await response.json();
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    setIsImpersonating(false);
    setAuthState({
      user,
      isAuthenticated: true,
      isLoading: false,
      permissions: user.permissions ?? [],
    });
  }, []);

  const contextValue = useMemo<AuthContextType>(() => ({
    ...authState,
    login,
    logout,
    isImpersonating,
    impersonate,
    stopImpersonating,
  }), [authState, login, logout, isImpersonating, impersonate, stopImpersonating]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}
