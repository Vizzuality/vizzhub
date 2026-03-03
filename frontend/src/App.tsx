import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './core/contexts/AuthContext';
import { ErrorBoundary } from './core/components/ErrorBoundary';
import { ProtectedRoute, AdminRoute } from './core/components/ProtectedRoute';
import { AppLayout } from './core/components/layout/AppLayout';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import GlobalDashboard from './pages/GlobalDashboard';
import Admin from './core/pages/Admin';
import ISO from './pages/ISO';
import ISOSnapshots from './pages/ISOSnapshots';
import ISOSnapshotDetail from './pages/iso/ISOSnapshotDetail';
import { LoginPage } from './core/pages/LoginPage';
import ConfigurationTab from './components/Settings/ConfigurationTab';
import IntegrationsTab from './components/Settings/IntegrationsTab';
import AdminNotificationsLayout from './core/components/NotificationsAdmin/AdminNotificationsLayout';
import AlertLogTab from './core/components/NotificationsAdmin/AlertLogTab';
import SilencesTab from './core/components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from './core/components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from './core/components/NotificationsAdmin/StatisticsTab';
import JobsContent from './core/components/Admin/JobsContent';
import { UsersContent } from './core/components/Admin/UsersContent';

const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === 'true';

function AdminRoutes(): JSX.Element {
  return (
    <>
      <Route path="global-scores" element={<GlobalDashboard />} />
      <Route path="scorecard-parameters" element={<ConfigurationTab />} />
      <Route path="integrations" element={<IntegrationsTab />} />
      <Route path="notifications" element={<AdminNotificationsLayout />}>
        <Route path="log" element={<AlertLogTab />} />
        <Route path="silences" element={<SilencesTab />} />
        <Route path="config" element={<AlertConfigTab />} />
        <Route path="stats" element={<StatisticsTab />} />
      </Route>
      <Route path="jobs" element={<JobsContent />} />
      <Route path="users" element={<UsersContent />} />
    </>
  );
}

function AppRoutes(): JSX.Element {
  if (BYPASS_AUTH) {
    return (
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/scorecard" replace />} />
          <Route path="/scorecard" element={<Projects />} />
          <Route path="/scorecard/:id" element={<ProjectDetail />} />
          <Route path="/admin" element={<Admin />}>
            {AdminRoutes()}
          </Route>
          <Route path="/iso" element={<ISO />}>
            <Route path="snapshots" element={<ISOSnapshots />} />
            <Route path="snapshots/:id" element={<ISOSnapshotDetail />} />
          </Route>
        </Route>
        <Route path="/login" element={<Navigate to="/scorecard" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/scorecard" replace />} />
          <Route path="/scorecard" element={<Projects />} />
          <Route path="/scorecard/:id" element={<ProjectDetail />} />
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<Admin />}>
              {AdminRoutes()}
            </Route>
            <Route path="/iso" element={<ISO />}>
              <Route path="snapshots" element={<ISOSnapshots />} />
              <Route path="snapshots/:id" element={<ISOSnapshotDetail />} />
            </Route>
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

function App(): JSX.Element {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
