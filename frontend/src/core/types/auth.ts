/**
 * Authentication types for Google OAuth integration
 */

export type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserPublic {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
}

export interface AuthLoginResponse {
  user: UserPublic;
}

export interface AuthState {
  user: UserPublic | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
}
