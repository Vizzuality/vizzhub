/**
 * Protected route wrapper - redirects to login if not authenticated
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

export function ProtectedRoute(): JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

/**
 * Admin route wrapper - redirects to /scorecard if not admin
 */
export function AdminRoute(): JSX.Element {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/scorecard" replace />;
  }

  return <Outlet />;
}
