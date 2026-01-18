/**
 * Authentication types for Google OAuth integration
 *
 * TODO: Google OAuth implementation pending
 * Expected flow:
 * 1. User clicks "Sign in with Google"
 * 2. Google OAuth flow completes
 * 3. Backend receives Google token and issues JWT
 * 4. Frontend stores JWT and includes it in all API requests
 */

export interface User {
  id: string;
  email: string;
  name?: string;
  picture?: string;
  domain?: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: () => Promise<void>;
  logout: () => void;
  setToken: (token: string) => void;
  getToken: () => string | null;
}
