import { useContext } from 'react';
import { AuthContext } from '@/core/contexts/AuthContext';
import type { Permission } from './constants';

function usePermissionsList(): string[] {
  // Tolerate test renders that don't include AuthProvider — return an empty
  // permission set so any check resolves to false (no write affordances).
  const ctx = useContext(AuthContext);
  return ctx?.permissions ?? [];
}

export function usePermissions(...perms: Permission[]): boolean {
  const permissions = usePermissionsList();
  if (permissions.includes('*')) return true;
  return perms.every((p) => permissions.includes(p));
}

export function useAnyPermission(...perms: Permission[]): boolean {
  const permissions = usePermissionsList();
  if (permissions.includes('*')) return true;
  return perms.some((p) => permissions.includes(p));
}

export function usePermission(permission: Permission): boolean {
  return usePermissions(permission);
}
