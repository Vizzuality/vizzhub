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

import { Routes, Route, Link, Navigate } from 'react-router-dom';
import { LayoutDashboard, FolderKanban, Settings } from 'lucide-react';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './hooks/useAuth';
import ProjectList from './pages/ProjectList';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
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
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-gray-200 p-6">
        <h1 className="text-xl font-bold text-primary-600 mb-8">
          Project Scorecard
        </h1>
        <nav className="space-y-2">
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <LayoutDashboard className="w-5 h-5" />
            Dashboard
          </Link>
          <Link
            to="/projects"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <FolderKanban className="w-5 h-5" />
            Projects
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <Settings className="w-5 h-5" />
            Settings
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-8">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
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
