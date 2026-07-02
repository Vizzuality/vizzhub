import type { ClientRow, ProjectRow } from '../types/portfolio';

function fmtEur(v: number | null): string {
  return v === null ? '—' : `€${Math.round(v).toLocaleString()}`;
}
function fmtPct(v: number | null): string {
  return v === null ? '—' : `${v.toFixed(1)}%`;
}
function fmtDelay(v: number | null): string {
  if (v === null) return '—';
  const sign = v > 0 ? '+' : '';
  return `${sign}${v}mo`;
}

const HEAD_ROW =
  'border-b text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground';
const BODY_ROW = 'border-b border-border/50 hover:bg-muted/40 transition-colors';

export function ProjectTable({ rows }: { readonly rows: ProjectRow[] }): JSX.Element {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className={HEAD_ROW}>
          <th className="py-2 font-medium">Project</th>
          <th className="font-medium">Client</th>
          <th className="text-right font-medium">Margin %</th>
          <th className="text-right font-medium">Profit €</th>
          <th className="text-right font-medium">Delay</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.project_id} className={BODY_ROW}>
            <td className="py-2 font-medium">{r.name}</td>
            <td className="text-muted-foreground">{r.client_name ?? '—'}</td>
            <td className="text-right tabular-nums">{fmtPct(r.margin_pct)}</td>
            <td className="text-right tabular-nums">{fmtEur(r.profit_eur)}</td>
            <td className="text-right tabular-nums">{fmtDelay(r.delay_months)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ClientTable({ rows }: { readonly rows: ClientRow[] }): JSX.Element {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className={HEAD_ROW}>
          <th className="py-2 font-medium">Client</th>
          <th className="text-right font-medium">Projects</th>
          <th className="text-right font-medium">Margin %</th>
          <th className="text-right font-medium">Profit €</th>
          <th className="text-right font-medium">Delay</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.client_id ?? r.client_name} className={BODY_ROW}>
            <td className="py-2 font-medium">{r.client_name}</td>
            <td className="text-right tabular-nums">{r.project_count}</td>
            <td className="text-right tabular-nums">{fmtPct(r.margin_pct)}</td>
            <td className="text-right tabular-nums">{fmtEur(r.profit_eur)}</td>
            <td className="text-right tabular-nums">{fmtDelay(r.delay_months)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
