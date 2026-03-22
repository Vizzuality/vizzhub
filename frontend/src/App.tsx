import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './core/contexts/AuthContext';
import { ErrorBoundary } from './core/components/ErrorBoundary';
import { ProtectedRoute } from './core/components/ProtectedRoute';
import { PermissionRoute, Action } from './core/permissions';
import { AppLayout } from './core/components/layout/AppLayout';
import CoreProjects from './core/pages/Projects';
import ProjectFormPage from './core/pages/ProjectForm';
import ScorecardProjects from './modules/scorecard/pages/Projects';
import ProjectDetail from './modules/scorecard/pages/ProjectDetail';
import GlobalDashboard from './modules/scorecard/pages/GlobalDashboard';
import Admin from './core/pages/Admin';
import ISO from './modules/iso/pages/ISO';
import ISOSnapshots from './modules/iso/pages/ISOSnapshots';
import ISOSnapshotDetail from './modules/iso/pages/ISOSnapshotDetail';
import { LoginPage } from './core/pages/LoginPage';
import TrackerLayout from './modules/tracker/components/TrackerLayout';
import ReportingPeriods from './modules/tracker/pages/ReportingPeriods';
import PeriodDetail from './modules/tracker/pages/PeriodDetail';
import MyReport from './modules/tracker/pages/MyReport';
import MyReportHistory from './modules/tracker/pages/MyReportHistory';
import HowToReport from './modules/tracker/pages/HowToReport';
import ProjectTrackerDetail from './modules/tracker/pages/ProjectTrackerDetail';
import AdminInvoices from './modules/tracker/pages/AdminInvoices';
import ConfigurationTab from './modules/scorecard/components/Settings/ConfigurationTab';
import IntegrationsTab from './modules/scorecard/components/Settings/IntegrationsTab';
import AdminNotificationsLayout from './core/components/NotificationsAdmin/AdminNotificationsLayout';
import AlertLogTab from './core/components/NotificationsAdmin/AlertLogTab';
import SilencesTab from './core/components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from './core/components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from './core/components/NotificationsAdmin/StatisticsTab';
import CustomNotificationTab from './core/components/NotificationsAdmin/CustomNotificationTab';
import JobsContent from './core/components/Admin/JobsContent';
import { UsersContent } from './core/components/Admin/UsersContent';
import UserDetail from './core/pages/UserDetail';
import Landing from './core/pages/Landing';
import CapacityInsights from './modules/capacity/pages/Insights';

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
        <Route path="custom" element={<CustomNotificationTab />} />
      </Route>
      <Route path="tracker" element={<TrackerLayout />}>
        <Route path="periods" element={<ReportingPeriods />} />
        <Route path="periods/:periodId" element={<PeriodDetail />} />
        <Route path="invoices" element={<AdminInvoices />} />
      </Route>
      <Route path="jobs" element={<JobsContent />} />
      <Route path="users" element={<UsersContent />} />
      <Route path="users/:userId" element={<UserDetail />} />
    </>
  );
}

function AppRoutes(): JSX.Element {
  if (BYPASS_AUTH) {
    return (
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/projects" element={<CoreProjects />} />
          <Route path="/projects/new" element={<ProjectFormPage />} />
          <Route path="/projects/:id/edit" element={<ProjectFormPage />} />
          <Route path="/scorecard" element={<ScorecardProjects />} />
          <Route path="/scorecard/:id" element={<ProjectDetail />} />
          <Route path="/admin" element={<Admin />}>
            {AdminRoutes()}
          </Route>
          <Route path="/iso" element={<ISO />}>
            <Route path="snapshots" element={<ISOSnapshots />} />
            <Route path="snapshots/:id" element={<ISOSnapshotDetail />} />
          </Route>
          <Route path="/tracker/my-report" element={<MyReport />} />
          <Route path="/tracker/my-report/:periodId" element={<MyReport />} />
          <Route path="/tracker/my-reports" element={<MyReportHistory />} />
          <Route path="/tracker/how-to-report" element={<HowToReport />} />
          <Route path="/tracker/projects/:projectId" element={<ProjectTrackerDetail />} />
          <Route path="/capacity/insights" element={<CapacityInsights />} />
        </Route>
        <Route path="/login" element={<Navigate to="/projects" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/projects" element={<CoreProjects />} />
          <Route path="/projects/new" element={<ProjectFormPage />} />
          <Route path="/projects/:id/edit" element={<ProjectFormPage />} />
          <Route path="/scorecard" element={<ScorecardProjects />} />
          <Route path="/scorecard/:id" element={<ProjectDetail />} />
          <Route path="/tracker/my-report" element={<MyReport />} />
          <Route path="/tracker/my-report/:periodId" element={<MyReport />} />
          <Route path="/tracker/my-reports" element={<MyReportHistory />} />
          <Route path="/tracker/how-to-report" element={<HowToReport />} />
          <Route path="/tracker/projects/:projectId" element={<ProjectTrackerDetail />} />
          <Route path="/capacity/insights" element={<CapacityInsights />} />
          <Route element={<PermissionRoute require={Action.ADMIN_USERS} />}>
            <Route path="/admin" element={<Admin />}>
              {AdminRoutes()}
            </Route>
          </Route>
          <Route element={<PermissionRoute require={Action.ISO_VIEW} />}>
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
