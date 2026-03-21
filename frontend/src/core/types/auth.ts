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
  active: boolean;
  functional_area_id: string | null;
  rate_id: string | null;
  dedication: number | null;
  slack_user_id: string | null;
  slack_display_name: string | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  is_impersonating?: boolean;
}

export interface FunctionalArea {
  id: string;
  name: string;
}

export interface Rate {
  id: string;
  code: string;
  value: number;
}

export interface UserPublic {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
  active: boolean;
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
  isImpersonating: boolean;
  impersonate: (userId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
}
