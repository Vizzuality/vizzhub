/**
 * Main Application Component
 *
 * Authentication Flow:
 * - Development mode: BYPASS_AUTH=true allows unauthenticated access
 * - Production mode: Requires Google OAuth authentication
 * - All routes except /login are protected
 */


import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import GlobalDashboard from './pages/GlobalDashboard';
import Admin from './pages/Admin';
import { LoginPage } from './pages/LoginPage';

// Development mode: bypass authentication
// Set to false to require Google OAuth
const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === 'true';

function AppRoutes(): JSX.Element {
  // In bypass mode, render routes without protection
  if (BYPASS_AUTH) {
    return (
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/global" element={<GlobalDashboard />} />
          <Route path="/admin" element={<Admin />} />
        </Route>
        <Route path="/login" element={<Navigate to="/projects" replace />} />
      </Routes>
    );
  }

  // Production mode with authentication
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/global" element={<GlobalDashboard />} />
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

function App(): JSX.Element {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
