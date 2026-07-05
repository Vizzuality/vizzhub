import { useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { usePrograms } from '@/core/hooks/usePrograms';
import {
  useApplyOverview,
  useCurrentImportBatch,
  useImportProjects,
  useOverviewMatches,
  useSaveDecision,
  useUploadOverview,
} from '../hooks/useOverviewImport';
import { ProjectPicker } from '../components/ProjectPicker';
import { ProgramPicker } from '../components/ProgramPicker';
import type {
  OverviewDecision,
  OverviewProjectCandidate,
} from '../types/portfolio';
import { mergePrograms, seedDecisions, type DecisionMap } from '../utils/importDecisions';

export default function PortfolioImport(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<DecisionMap>({});
  // Set when the user explicitly starts over, so we stop auto-resuming the batch
  // that useCurrentImportBatch still returns and let the upload dropzone appear.
  const [dismissed, setDismissed] = useState(false);
  const current = useCurrentImportBatch();
  const upload = useUploadOverview();
  const apply = useApplyOverview();
  const save = useSaveDecision();
  const { data: matches, isLoading } = useOverviewMatches(batchId);
  const { data: programs = [] } = usePrograms();
  const { data: importProjects = [] } = useImportProjects();

  const allProjects: OverviewProjectCandidate[] = useMemo(
    () => importProjects.map((p) => ({ id: p.id, name: p.name, score: 0 })),
    [importProjects],
  );
  const programByProject = useMemo(
    () => new Map(importProjects.map((p) => [p.id, p.program_id])),
    [importProjects],
  );

  // Resume an in-progress batch on load. Skipped once the user starts over — a
  // page reload remounts with dismissed=false, so resume-on-reload still works.
  useEffect(() => {
    if (!batchId && current.data && !dismissed) {
      setBatchId(current.data.batch_id);
    }
  }, [batchId, current.data, dismissed]);

  // Seed the editable map from persisted decisions when matches arrive.
  useEffect(() => {
    if (matches && matches.length > 0) {
      setDecisions((prev) => (Object.keys(prev).length === 0 ? seedDecisions(matches) : prev));
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

  // Local optimistic update + persist the row's decision. Compute the merged decision from the
  // current render's state, apply it locally, then fire the PATCH — never call the mutation inside
  // the setState updater (that side-effects a reducer and double-fires under React StrictMode).
  const patch = (id: string, p: Partial<OverviewDecision>): void => {
    const next: OverviewDecision = { ...decisions[id], ...p, staging_id: id };
    setDecisions((prev) => ({ ...prev, [id]: next }));
    if (batchId) {
      save.mutate({
        batchId,
        stagingId: id,
        patch: {
          project_id: next.project_id ?? null,
          program_action: next.program_action,
          program_id: next.program_id ?? null,
          new_program_name: next.new_program_name ?? null,
        },
      });
    }
  };

  const showUpload = !batchId;

  return (
    <div className="space-y-4">
      {showUpload && (
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
            <span className="text-sm text-muted-foreground">
              {matches.length} rows ·{' '}
              {save.isError ? (
                <span className="text-aux-yellow">
                  A change failed to save — reload to see the saved state
                </span>
              ) : save.isPending ? (
                'Saving…'
              ) : (
                'changes save automatically'
              )}
            </span>
            <div className="flex items-center gap-2">
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="outline">Start over</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Discard the review in progress?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Uploading a new spreadsheet discards the current review and its saved
                      decisions.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => {
                        setBatchId(null);
                        setDecisions({});
                        setDismissed(true);
                      }}
                    >
                      Discard &amp; upload new
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              <Button onClick={() => apply.mutate(batchId)} disabled={apply.isPending}>
                Apply
              </Button>
            </div>
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
                        if (pid) {
                          const projectProgram = programByProject.get(pid) ?? null;
                          patch(m.staging_id, {
                            project_id: pid,
                            program_action: projectProgram
                              ? 'inherit'
                              : m.suggested_program.program_id
                                ? 'link'
                                : 'create',
                            program_id: projectProgram ?? m.suggested_program.program_id ?? null,
                            new_program_name:
                              allProjects.find((p) => p.id === pid)?.name ?? m.name,
                          });
                        } else {
                          patch(m.staging_id, {
                            project_id: null,
                            program_action: m.suggested_program.program_id ? 'link' : 'create',
                            program_id: m.suggested_program.program_id ?? null,
                            new_program_name: m.name,
                          });
                        }
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
                      programs={mergePrograms(m.program_candidates, programs)}
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
                      onNone={() => patch(m.staging_id, { program_action: 'none', program_id: null })}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {apply.data && (
            <output className="block rounded-md border p-3 text-sm">
              Applied {apply.data.applied} · programs created {apply.data.programs_created} ·
              programs annotated {apply.data.programs_annotated} · linked{' '}
              {apply.data.projects_linked_to_program} · skipped {apply.data.skipped}
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
