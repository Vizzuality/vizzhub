import { Routes, Route, Navigate } from 'react-router-dom';
import * as Sentry from '@sentry/react';
import { AuthProvider } from './core/contexts/AuthContext';
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
import InvoiceDetail from './modules/tracker/pages/InvoiceDetail';
import Moods from './modules/tracker/pages/Moods';
import ConfigurationTab from './modules/scorecard/components/Settings/ConfigurationTab';
import IntegrationsTab from './modules/scorecard/components/Settings/IntegrationsTab';
import AdminNotificationsLayout from './core/components/NotificationsAdmin/AdminNotificationsLayout';
import AlertLogTab from './core/components/NotificationsAdmin/AlertLogTab';
import SilencesTab from './core/components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from './core/components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from './core/components/NotificationsAdmin/StatisticsTab';
import CustomNotificationTab from './core/components/NotificationsAdmin/CustomNotificationTab';
import { AssetsContent } from './core/components/Admin/AssetsContent';
import CommandsContent from './core/components/Admin/CommandsContent';
import JobsContent from './core/components/Admin/JobsContent';
import { UsersContent } from './core/components/Admin/UsersContent';
import { RatesContent } from './core/components/Admin/RatesContent';
import UserDetail from './core/pages/UserDetail';
import Landing from './core/pages/Landing';
import CapacityInsights from './modules/capacity/pages/Insights';
import CapacityAllocation from './modules/capacity/pages/Allocation';
import CapacityPlanner from './modules/capacity/pages/Planner';
import Playbook from './modules/playbook/pages/Playbook';
import Events from './modules/events/pages/Events';
import EventsDashboard from './modules/events/pages/EventsDashboard';
import DevstackCatalog from './modules/devstack/pages/Catalog';
import IsoDocs from './modules/iso-docs/pages/IsoDocs';
import IsoNotesAdmin from './modules/iso-docs/pages/IsoNotesAdmin';
import NotFound from './core/pages/NotFound';

const SentryRoutes = Sentry.withSentryReactRouterV6Routing(Routes);

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
        <Route path="invoices/:invoiceId" element={<InvoiceDetail />} />
        <Route path="moods" element={<Moods />} />
        <Route path="rates" element={<RatesContent />} />
      </Route>
      <Route path="iso/notes" element={<IsoNotesAdmin />} />
      <Route path="assets" element={<AssetsContent />} />
      <Route path="jobs" element={<JobsContent />} />
      <Route path="commands" element={<CommandsContent />} />
      <Route path="users" element={<UsersContent />} />
      <Route path="users/:userId" element={<UserDetail />} />
    </>
  );
}

function AppRoutes(): JSX.Element {
  if (BYPASS_AUTH) {
    return (
      <SentryRoutes>
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
          <Route path="/tracker/invoices/:invoiceId" element={<InvoiceDetail />} />
          <Route path="/capacity/insights" element={<CapacityInsights />} />
          <Route path="/capacity/allocation" element={<CapacityAllocation />} />
          <Route path="/capacity/planner" element={<CapacityPlanner />} />
          <Route path="/playbook" element={<Playbook />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/dashboard" element={<EventsDashboard />} />
          <Route path="/devstack" element={<DevstackCatalog />} />
          <Route path="/iso/docs" element={<IsoDocs />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="/login" element={<Navigate to="/projects" replace />} />
      </SentryRoutes>
    );
  }

  return (
    <SentryRoutes>
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
          <Route element={<PermissionRoute require={Action.TRACKER_MANAGE} />}>
            <Route path="/tracker/invoices/:invoiceId" element={<InvoiceDetail />} />
          </Route>
          <Route path="/capacity/insights" element={<CapacityInsights />} />
          <Route path="/capacity/allocation" element={<CapacityAllocation />} />
          <Route path="/capacity/planner" element={<CapacityPlanner />} />
          <Route path="/playbook" element={<Playbook />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/dashboard" element={<EventsDashboard />} />
          <Route path="/devstack" element={<DevstackCatalog />} />
          <Route element={<PermissionRoute require={Action.ADMIN_USERS} />}>
            <Route path="/admin" element={<Admin />}>
              {AdminRoutes()}
            </Route>
          </Route>
          <Route path="/iso/docs" element={<IsoDocs />} />
          <Route element={<PermissionRoute require={Action.ISO_VIEW} />}>
            <Route path="/iso" element={<ISO />}>
              <Route path="snapshots" element={<ISOSnapshots />} />
              <Route path="snapshots/:id" element={<ISOSnapshotDetail />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </SentryRoutes>
  );
}

function ErrorFallback({ error }: { error: unknown }): JSX.Element {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="max-w-md w-full text-center space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Something went wrong</h1>
        <p className="text-muted-foreground">
          An unexpected error occurred. Please try refreshing the page.
        </p>
        {message && (
          <pre className="text-xs text-left bg-muted p-4 rounded-md overflow-auto max-h-40">
            {message}
          </pre>
        )}
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

const sentryFallback = ({ error }: { error: unknown }): JSX.Element => (
  <ErrorFallback error={error} />
);

function App(): JSX.Element {
  return (
    <Sentry.ErrorBoundary fallback={sentryFallback}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Sentry.ErrorBoundary>
  );
}

export default App;
