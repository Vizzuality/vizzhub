import { useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  useApplyOverview,
  useOverviewMatches,
  useUploadOverview,
} from '../hooks/useOverviewImport';
import type { OverviewDecision, OverviewMatch } from '../types/portfolio';

type DecisionMap = Record<string, OverviewDecision>;

function toInitialDecisions(matches: OverviewMatch[]): DecisionMap {
  const map: DecisionMap = {};
  for (const m of matches) {
    map[m.staging_id] = {
      staging_id: m.staging_id,
      action: m.suggested.action,
      program_id: m.suggested.program_id,
      project_id: m.suggested.project_id,
    };
  }
  return map;
}

export default function PortfolioImport(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<DecisionMap>({});
  const upload = useUploadOverview();
  const apply = useApplyOverview();
  const { data: matches, isLoading } = useOverviewMatches(batchId);

  const decisionList = useMemo(() => Object.values(decisions), [decisions]);

  // Seed per-row decisions from the backend's suggestions once matches arrive.
  useEffect(() => {
    if (matches && matches.length > 0) {
      setDecisions((prev) => (Object.keys(prev).length === 0 ? toInitialDecisions(matches) : prev));
    }
  }, [matches]);

  if (!canManage) {
    return <Navigate to="/admin/portfolio" replace />;
  }

  const onFile = async (file: File): Promise<void> => {
    const res = await upload.mutateAsync(file);
    setDecisions({});
    setBatchId(res.batch_id);
  };

  const setAction = (
    id: string,
    action: OverviewDecision['action'],
    programId?: string | null,
  ): void => {
    setDecisions((prev) => ({
      ...prev,
      [id]: { ...prev[id], action, program_id: programId ?? null, project_id: null },
    }));
  };

  return (
    <div className="space-y-4">
      {!batchId && (
        <div className="rounded-md border border-dashed p-6 text-center">
          <p className="mb-3 text-sm text-muted-foreground">
            Upload the Portfolio Overview spreadsheet (.xlsx) to stage rows for matching.
          </p>
          <input
            type="file"
            accept=".xlsx"
            aria-label="Overview spreadsheet"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onFile(f);
            }}
          />
          {upload.isPending && <LoadingSpinner className="mt-3" />}
        </div>
      )}

      {batchId && isLoading && <LoadingSpinner />}

      {batchId && matches && (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{matches.length} rows staged</span>
            <Button
              onClick={() => apply.mutate({ batchId, decisions: decisionList })}
              disabled={apply.isPending}
            >
              Apply {decisionList.length} decisions
            </Button>
          </div>

          <ul className="divide-y">
            {matches.map((m) => (
              <li key={m.staging_id} className="flex items-center justify-between gap-4 py-2">
                <div className="min-w-0">
                  <p className="truncate font-medium">{m.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {[m.client_type_raw, m.service_raw, m.impact_area_raw]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </div>
                <select
                  aria-label={`Match for ${m.name}`}
                  className="rounded border px-2 py-1 text-sm"
                  value={
                    decisions[m.staging_id]?.program_id ??
                    decisions[m.staging_id]?.action ??
                    'create'
                  }
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === 'create' || v === 'skip') setAction(m.staging_id, v);
                    else setAction(m.staging_id, 'link', v);
                  }}
                >
                  <option value="create">Create new program</option>
                  <option value="skip">Skip</option>
                  {m.candidates
                    .filter((c) => c.kind === 'program')
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        Link: {c.name} ({Math.round(c.score * 100)}%)
                      </option>
                    ))}
                </select>
              </li>
            ))}
          </ul>

          {apply.data && (
            <output className="block rounded-md border p-3 text-sm">
              Applied {apply.data.applied} · created {apply.data.created_programs} · linked{' '}
              {apply.data.linked} · skipped {apply.data.skipped}
              {apply.data.unmapped_terms.length > 0 && (
                <p className="mt-1 text-aux-yellow">
                  Unmapped terms: {apply.data.unmapped_terms.join(', ')}
                </p>
              )}
              {apply.data.unresolved_clients.length > 0 && (
                <p className="mt-1 text-aux-yellow">
                  Unresolved partners: {apply.data.unresolved_clients.join(', ')}
                </p>
              )}
            </output>
          )}
        </>
      )}
    </div>
  );
}
