import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { usePermission } from './usePermission';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import type { Permission } from './constants';

interface PermissionRouteProps {
  readonly require: Permission;
  readonly fallback?: string;
}

export function PermissionRoute({
  require,
  fallback = '/',
}: PermissionRouteProps): JSX.Element {
  const allowed = usePermission(require);
  const { isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  if (!allowed) {
    return <Navigate to={fallback} replace />;
  }

  return <Outlet />;
}
