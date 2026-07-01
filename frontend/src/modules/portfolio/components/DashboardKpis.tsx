import { Card, CardContent } from '@/shared/components/ui/card';
import { formatAxisEur } from '../utils/chart';
import type { PortfolioKpis } from '../types/portfolio';

function Kpi({ label, value }: { readonly label: string; readonly value: string }): JSX.Element {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}

export function DashboardKpis({ kpis }: { readonly kpis: PortfolioKpis }): JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Kpi label="Projects" value={String(kpis.project_count)} />
      <Kpi label="Total spend" value={formatAxisEur(kpis.total_spend_eur)} />
      <Kpi label="Clients" value={String(kpis.client_count)} />
      <Kpi
        label="Avg margin"
        value={kpis.avg_margin === null ? '—' : `${kpis.avg_margin.toFixed(1)}%`}
      />
    </div>
  );
}
