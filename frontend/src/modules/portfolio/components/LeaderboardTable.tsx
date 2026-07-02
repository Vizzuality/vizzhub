import type { ClientRow, ProjectRow } from '../types/portfolio';

function fmtEur(v: number | null): string {
  return v === null ? '—' : `€${Math.round(v).toLocaleString()}`;
}
function fmtPct(v: number | null): string {
  return v === null ? '—' : `${v.toFixed(1)}%`;
}
function fmtDelay(v: number | null): string {
  return v === null ? '—' : `${v > 0 ? '+' : ''}${v}m`;
}

export function ProjectTable({ rows }: { readonly rows: ProjectRow[] }): JSX.Element {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="py-1">Project</th><th>Client</th>
          <th className="text-right">Margin</th><th className="text-right">Profit</th>
          <th className="text-right">Delay</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.project_id} className="border-t">
            <td className="py-1">{r.name}</td>
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
        <tr className="text-left text-muted-foreground">
          <th className="py-1">Client</th><th className="text-right"># Proj.</th>
          <th className="text-right">Margin</th><th className="text-right">Profit</th>
          <th className="text-right">Delay</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.client_id ?? r.client_name} className="border-t">
            <td className="py-1">{r.client_name}</td>
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
