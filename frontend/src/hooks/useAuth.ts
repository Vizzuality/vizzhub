/**
 * Hook to access authentication context
 *
 * Usage:
 *   const { user, isAuthenticated, login, logout } = useAuth();
 *
 * This hook provides access to:
 * - user: Current authenticated user (null if not authenticated)
 * - isAuthenticated: Boolean indicating if user is logged in
 * - isLoading: Boolean indicating if auth state is being initialized
 * - login: Function to authenticate with Google credential
 * - logout: Function to clear authentication state
 * - getToken: Function to retrieve stored JWT token
 */

import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { AuthContextType } from '../types/auth';

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};
