/**
 * Main Application Component
 *
 * Authentication Flow:
 * - Development mode: BYPASS_AUTH=true allows unauthenticated access
 * - Production mode: Requires Google OAuth authentication
 * - Login page shown when not authenticated (and BYPASS_AUTH is false)
 * - AuthProvider wraps entire app to manage auth state
 *
 * TODO: Set BYPASS_AUTH to false when Google OAuth is implemented
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import { AppLayout } from './components/layout/AppLayout';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import GlobalDashboard from './pages/GlobalDashboard';
import SettingsPage from './pages/Settings';
import Login from './pages/Login';

// Development mode: bypass authentication
// TODO: Set to false when Google OAuth is implemented
const BYPASS_AUTH = true;

function AppContent(): JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  // In development mode or if authenticated, show the main app
  if (!BYPASS_AUTH && !isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      {/* Routes with navbar */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/global" element={<GlobalDashboard />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Routes without navbar */}
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}

function App(): JSX.Element {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
