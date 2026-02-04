/**
 * Authentication Context for Google OAuth
 */

import { createContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react';
import { UserPublic, AuthState, AuthContextType, AuthResponse } from '../types/auth';

const TOKEN_STORAGE_KEY = 'auth_token';
const USER_STORAGE_KEY = 'auth_user';
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_AUTH_STATE: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [authState, setAuthState] = useState<AuthState>(DEFAULT_AUTH_STATE);

  /**
   * Login with Google credential
   */
  const login = useCallback(async (credential: string): Promise<void> => {
    const response = await fetch(`${API_URL}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Authentication failed');
    }

    const data: AuthResponse = await response.json();

    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user));

    setAuthState({
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  /**
   * Clear authentication state and tokens
   */
  const logout = useCallback((): void => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  /**
   * Retrieve stored JWT token
   */
  const getToken = useCallback((): string | null => {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  }, []);

  /**
   * Validate token with backend
   */
  const validateToken = useCallback(async (token: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const user: UserPublic = await response.json();
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
        setAuthState({
          user,
          isAuthenticated: true,
          isLoading: false,
        });
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    const initAuth = async (): Promise<void> => {
      const token = localStorage.getItem(TOKEN_STORAGE_KEY);

      if (token) {
        const isValid = await validateToken(token);
        if (!isValid) {
          logout();
        }
      } else {
        setAuthState((prev) => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, [logout, validateToken]);

  const contextValue = useMemo<AuthContextType>(() => ({
    ...authState,
    login,
    logout,
    getToken,
  }), [authState, login, logout, getToken]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}
