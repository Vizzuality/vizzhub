import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import type { DashboardKpis as Kpis } from '@/modules/accrual/types/accrual';

interface DashboardKpisProps {
  readonly kpis: Kpis;
}

interface KpiCardProps {
  readonly label: string;
  readonly value: string;
}

function KpiCard({ label, value }: KpiCardProps): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <span className="text-2xl font-semibold">{value}</span>
      </CardContent>
    </Card>
  );
}

export function DashboardKpis({ kpis }: DashboardKpisProps): JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <KpiCard label="Recognized YTD" value={formatCurrency(kpis.recognized_ytd_eur)} />
      <KpiCard label="This quarter" value={formatCurrency(kpis.recognized_quarter_eur)} />
      <KpiCard label="Backlog" value={formatCurrency(kpis.backlog_eur)} />
      <KpiCard label="Manual share" value={`${kpis.manual_pct.toFixed(1)}%`} />
    </div>
  );
}
