import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import type { DashboardKpis as Kpis } from '@/modules/accrual/types/accrual';

interface DashboardKpisProps {
  readonly kpis: Kpis;
}

type KpiTone = 'default' | 'positive' | 'negative';

interface KpiCardProps {
  readonly label: string;
  readonly value: string;
  readonly sub?: string;
  readonly tone?: KpiTone;
}

const TONE_CLASS: Record<KpiTone, string> = {
  default: '',
  positive: 'text-[var(--score-green)]',
  negative: 'text-[var(--score-red)]',
};

function KpiCard({ label, value, sub, tone = 'default' }: KpiCardProps): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <span className={`text-2xl font-semibold ${TONE_CLASS[tone]}`}>{value}</span>
        {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

/** YoY card content: arrow + signed %, with both compared figures as the subtitle.
 * Falls back to an em-dash when there is no prior-year recognition to compare. */
function yoyCardProps(kpis: Kpis): Pick<KpiCardProps, 'value' | 'sub' | 'tone'> {
  if (kpis.yoy_pct === null) {
    return { value: '—', sub: 'No prior-year data', tone: 'default' };
  }
  const up = kpis.yoy_pct >= 0;
  return {
    value: `${up ? '▲' : '▼'} ${up ? '+' : ''}${kpis.yoy_pct.toFixed(1)}%`,
    sub: `${formatCurrency(kpis.recognized_ytd_eur)} vs ${formatCurrency(
      kpis.recognized_prev_ytd_eur,
    )}`,
    tone: up ? 'positive' : 'negative',
  };
}

export function DashboardKpis({ kpis }: DashboardKpisProps): JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <KpiCard label="Recognized YTD" value={formatCurrency(kpis.recognized_ytd_eur)} />
      <KpiCard label="This quarter" value={formatCurrency(kpis.recognized_quarter_eur)} />
      <KpiCard label="Backlog" value={formatCurrency(kpis.backlog_eur)} />
      <KpiCard label="Year plan recognized" value={`${kpis.plan_recognized_pct.toFixed(0)}%`} />
      <KpiCard label="vs Last Year" {...yoyCardProps(kpis)} />
    </div>
  );
}
