/**
 * Authentication Context for managing user authentication state
 *
 * IMPORTANT: This is prepared for Google OAuth integration
 * Currently in development mode - authentication is optional
 *
 * TODO: Implement Google OAuth flow
 * - Add Google Sign-In library
 * - Implement handleGoogleLogin function
 * - Exchange Google token for backend JWT
 * - Handle token refresh
 *
 * Production flow:
 * 1. User initiates Google OAuth via login()
 * 2. Backend validates Google token and returns JWT
 * 3. JWT stored in localStorage
 * 4. All API requests include JWT in Authorization header
 * 5. Backend validates JWT for protected routes
 */

import React, { createContext, useState, useEffect, ReactNode } from 'react';
import { User, AuthState, AuthContextType } from '../types/auth';

const TOKEN_STORAGE_KEY = 'auth_token';
const USER_STORAGE_KEY = 'auth_user';

const defaultAuthState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>(defaultAuthState);

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    const initAuth = (): void => {
      const token = localStorage.getItem(TOKEN_STORAGE_KEY);
      const userJson = localStorage.getItem(USER_STORAGE_KEY);

      if (token && userJson) {
        try {
          const user = JSON.parse(userJson) as User;
          setAuthState({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          console.error('Failed to parse stored user data:', error);
          logout();
        }
      } else {
        setAuthState((prev) => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, []);

  /**
   * TODO: Implement Google OAuth login flow
   *
   * Expected implementation:
   * 1. Trigger Google Sign-In popup
   * 2. Get Google OAuth token
   * 3. Send token to backend /api/oauth/google/callback
   * 4. Backend validates token and returns JWT + user info
   * 5. Store JWT and user in localStorage
   * 6. Update auth state
   */
  const login = async (): Promise<void> => {
    // Placeholder for Google OAuth implementation
    console.log('TODO: Implement Google OAuth login');
    throw new Error('Google OAuth not yet implemented');
  };

  /**
   * Clear authentication state and tokens
   */
  const logout = (): void => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    setAuthState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  };

  /**
   * Store JWT token and user information
   * Used after successful OAuth flow
   */
  const setToken = (token: string): void => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    // TODO: Decode JWT to extract user info or fetch from /api/me endpoint
    // For now, we'll need user info passed separately or decoded from JWT
  };

  /**
   * Retrieve stored JWT token
   */
  const getToken = (): string | null => {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  };

  const contextValue: AuthContextType = {
    ...authState,
    login,
    logout,
    setToken,
    getToken,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};
