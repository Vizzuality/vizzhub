import { lazy } from 'react';

export interface WidgetProps {
  readonly nodeId: string;
  readonly isEditor: boolean;
}

const KpiDashboard = lazy(() => import('./KpiDashboard'));

export const WIDGET_REGISTRY: Record<string, React.ComponentType<WidgetProps>> = {
  kpis: KpiDashboard,
  kpi_dashboard: KpiDashboard,
};
