/**
 * Authentication Context for Google OAuth
 *
 * JWT is stored in an httpOnly cookie (set by the backend).
 * A session hint flag in localStorage avoids unnecessary /auth/me calls
 * on mount when no session exists. Actual user data comes from the API.
 */

import { createContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react';
import { UserPublic, AuthState, AuthContextType, AuthLoginResponse } from '../types/auth';

const SESSION_HINT_KEY = 'auth_session';
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

export function AuthProvider({ children }: Readonly<AuthProviderProps>): JSX.Element {
  const [authState, setAuthState] = useState<AuthState>(DEFAULT_AUTH_STATE);
  const [isImpersonating, setIsImpersonating] = useState<boolean>(false);

  /**
   * Login with Google credential.
   * Backend sets the httpOnly cookie; we store a session hint locally.
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

    localStorage.setItem(SESSION_HINT_KEY, '1');

    setAuthState({
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
      permissions: data.user.permissions ?? [],
    });
  }, []);

  /**
   * Logout: ask backend to clear the cookie, then clear local session hint.
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

    localStorage.removeItem(SESSION_HINT_KEY);
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
        localStorage.setItem(SESSION_HINT_KEY, '1');
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

  // On mount: if session hint exists, validate the cookie; otherwise skip
  useEffect(() => {
    const initAuth = async (): Promise<void> => {
      const hasSession = localStorage.getItem(SESSION_HINT_KEY);

      if (hasSession) {
        const isValid = await validateSession();
        if (!isValid) {
          localStorage.removeItem(SESSION_HINT_KEY);
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
    localStorage.setItem(SESSION_HINT_KEY, '1');
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
    localStorage.setItem(SESSION_HINT_KEY, '1');
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
