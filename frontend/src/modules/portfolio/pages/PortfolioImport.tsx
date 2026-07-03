import { useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { usePrograms } from '@/core/hooks/usePrograms';
import {
  useApplyOverview,
  useImportProjects,
  useOverviewMatches,
  useUploadOverview,
} from '../hooks/useOverviewImport';
import { ProjectPicker } from '../components/ProjectPicker';
import { ProgramPicker } from '../components/ProgramPicker';
import type { OverviewDecision, OverviewMatch, OverviewProjectCandidate } from '../types/portfolio';

type DecisionMap = Record<string, OverviewDecision>;

function seed(matches: OverviewMatch[]): DecisionMap {
  const map: DecisionMap = {};
  for (const m of matches) {
    const pid = m.suggested_project.project_id;
    if (m.current_program.program_id) {
      map[m.staging_id] = {
        staging_id: m.staging_id,
        project_id: pid,
        program_action: 'inherit',
        program_id: m.current_program.program_id,
      };
    } else {
      const name = m.project_candidates.find((c) => c.id === pid)?.name ?? m.name;
      map[m.staging_id] = {
        staging_id: m.staging_id,
        project_id: pid,
        program_action: pid ? 'create' : 'none',
        new_program_name: name,
      };
    }
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
  const { data: programs = [] } = usePrograms();
  const { data: importProjects = [] } = useImportProjects();

  const decisionList = useMemo(() => Object.values(decisions), [decisions]);

  const allProjects: OverviewProjectCandidate[] = useMemo(
    () => importProjects.map((p) => ({ id: p.id, name: p.name, score: 0 })),
    [importProjects],
  );

  // Look up a project's real program to derive program context when the reviewer
  // picks any project (not just the server-suggested one).
  const programByProject = useMemo(
    () => new Map(importProjects.map((p) => [p.id, p.program_id])),
    [importProjects],
  );

  useEffect(() => {
    if (matches && matches.length > 0) {
      setDecisions((prev) => (Object.keys(prev).length === 0 ? seed(matches) : prev));
    }
  }, [matches]);

  if (!canManage) {
    return <Navigate to="/admin/portfolio" replace />;
  }

  const onFile = async (file: File): Promise<void> => {
    setDecisions({});
    const res = await upload.mutateAsync(file);
    setBatchId(res.batch_id);
  };

  const patch = (id: string, p: Partial<OverviewDecision>): void =>
    setDecisions((prev) => ({ ...prev, [id]: { ...prev[id], ...p } }));

  return (
    <div className="space-y-4">
      {!batchId && (
        <div className="rounded-md border border-dashed p-6 text-center">
          <p className="mb-3 text-sm text-muted-foreground">
            Upload the Portfolio Overview spreadsheet (.xlsx).
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
            {matches.map((m) => {
              const d = decisions[m.staging_id];
              return (
                <li key={m.staging_id} className="flex items-center justify-between gap-4 py-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {m.name}
                      {m.is_old_project && (
                        <span className="ml-2 rounded bg-muted px-1 text-xs">old</span>
                      )}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {[m.client_type_raw, m.service_raw, m.impact_area_raw]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <ProjectPicker
                      value={d?.project_id ?? null}
                      candidates={m.project_candidates}
                      allProjects={allProjects}
                      onChange={(pid) => {
                        const projectProgram = pid ? (programByProject.get(pid) ?? null) : null;
                        patch(m.staging_id, {
                          project_id: pid,
                          program_action: pid ? (projectProgram ? 'inherit' : 'create') : 'none',
                          program_id: projectProgram,
                          new_program_name: pid
                            ? (allProjects.find((p) => p.id === pid)?.name ?? m.name)
                            : null,
                        });
                      }}
                    />
                    <ProgramPicker
                      action={d?.program_action ?? 'none'}
                      programId={d?.program_id ?? null}
                      inheritedName={
                        d?.program_id
                          ? (programs.find((p) => p.id === d.program_id)?.name ?? null)
                          : m.current_program.name
                      }
                      programs={programs}
                      onLink={(pid) =>
                        patch(m.staging_id, { program_action: 'link', program_id: pid })
                      }
                      onCreate={() =>
                        patch(m.staging_id, {
                          program_action: 'create',
                          program_id: null,
                          new_program_name: m.name,
                        })
                      }
                      onNone={() =>
                        patch(m.staging_id, { program_action: 'none', program_id: null })
                      }
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {apply.data && (
            <output className="block rounded-md border p-3 text-sm">
              Applied {apply.data.applied} · programs created {apply.data.programs_created} ·
              linked {apply.data.projects_linked_to_program} · skipped {apply.data.skipped}
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
