import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { useAnyPermission, usePermission } from './usePermission';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import type { Permission } from './constants';

type PermissionRouteProps =
  | { readonly require: Permission; readonly requireAny?: never; readonly fallback?: string }
  | { readonly require?: never; readonly requireAny: readonly Permission[]; readonly fallback?: string };

export function PermissionRoute(props: PermissionRouteProps): JSX.Element {
  const { fallback = '/' } = props;
  const singleAllowed = usePermission(props.require ?? ('__never__' as Permission));
  const anyAllowed = useAnyPermission(...(props.requireAny ?? []));
  const allowed = props.requireAny ? anyAllowed : singleAllowed;
  const { isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  if (!allowed) {
    return <Navigate to={fallback} replace />;
  }

  return <Outlet />;
}
