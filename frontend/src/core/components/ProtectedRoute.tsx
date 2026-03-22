/**
 * Protected route wrapper - redirects to login if not authenticated
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
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
