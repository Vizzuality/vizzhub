import { useAuth } from '@/core/hooks/useAuth';
import type { Permission } from './constants';

export function usePermission(permission: Permission): boolean {
  const { permissions } = useAuth();
  return permissions.includes('*') || permissions.includes(permission);
}

export function usePermissions(...perms: Permission[]): boolean {
  const { permissions } = useAuth();
  if (permissions.includes('*')) return true;
  return perms.every((p) => permissions.includes(p));
}
