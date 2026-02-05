/**
 * Protected route wrapper - redirects to login if not authenticated
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function ProtectedRoute(): JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

/**
 * Admin route wrapper - redirects to /projects if not admin
 */
export function AdminRoute(): JSX.Element {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (user?.role !== 'admin') {
    return <Navigate to="/projects" replace />;
  }

  return <Outlet />;
}
