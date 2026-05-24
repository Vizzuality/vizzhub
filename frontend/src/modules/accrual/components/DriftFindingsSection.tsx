import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { useDriftFindings, useReopenDrift, useResolveDrift } from '@/modules/accrual/hooks/useUnmatched';
import type { DriftFinding, DriftKind } from '@/modules/accrual/types/accrual';

const DRIFT_KIND_LABELS: Record<DriftKind, string> = {
  date_extend: 'Date extend',
  date_shrink: 'Date shrink',
  value_drift: 'Value drift',
  status_stale: 'Status stale',
  missing_excel: 'Missing in Excel',
  missing_tracker: 'Missing in tracker',
};

const KIND_BADGE_CLASS: Record<DriftKind, string> = {
  date_extend: 'text-amber-600',
  date_shrink: 'text-amber-600',
  value_drift: 'text-amber-600',
  status_stale: 'text-amber-600',
  missing_excel: 'text-muted-foreground',
  missing_tracker: 'text-muted-foreground',
};

interface DriftFindingsSectionProps {
  /** Restrict to specific drift kinds. When omitted, shows all (excluding missing_* which
   * are surfaced in their own dedicated sections). */
  readonly kinds?: DriftKind[];
  readonly title: string;
  readonly description?: string;
}

function PayloadSummary({ payload }: { readonly payload: Record<string, unknown> }): JSX.Element {
  const entries = Object.entries(payload).filter(([, v]) => v !== null && v !== '');
  if (entries.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <ul className="space-y-0.5 text-xs">
      {entries.map(([k, v]) => (
        <li key={k}>
          <span className="text-muted-foreground">{k}:</span> <span className="tabular-nums">{String(v)}</span>
        </li>
      ))}
    </ul>
  );
}

interface FindingRowProps {
  readonly finding: DriftFinding;
  /** Group index — used to alternate background between project groups. */
  readonly groupIndex: number;
  /** True when this row starts a new project group (top divider + project name + group action). */
  readonly isGroupStart: boolean;
  /** Total findings in the same project group (rendered as "1 of N" badge when > 1). */
  readonly groupSize: number;
  /** Position within the current group, 1-indexed. */
  readonly groupPos: number;
  /** Sibling findings in this same project group — used for group-level actions. */
  readonly groupFindings: DriftFinding[];
}

function FindingRow({
  finding,
  groupIndex,
  isGroupStart,
  groupSize,
  groupPos,
  groupFindings,
}: FindingRowProps): JSX.Element {
  const [noteMode, setNoteMode] = useState(false);
  const [note, setNote] = useState('');
  const resolveMut = useResolveDrift();
  const reopenMut = useReopenDrift();

  const isGroup = groupSize > 1;
  // Pending findings in the group (for "Accept all" / "+ Note all" — group action
  // only ever touches what's still open; resolved siblings are left alone).
  const groupPending = groupFindings.filter((f) => !f.resolved_at);

  const acceptOne = (): void => {
    resolveMut.mutate({ id: finding.id, resolution: 'Accepted' });
  };

  const acceptAll = async (): Promise<void> => {
    await Promise.all(
      groupPending.map((f) =>
        resolveMut.mutateAsync({ id: f.id, resolution: 'Accepted' }),
      ),
    );
  };

  const saveNoteOne = async (): Promise<void> => {
    if (!note.trim()) return;
    await resolveMut.mutateAsync({ id: finding.id, resolution: note });
    setNoteMode(false);
    setNote('');
  };

  const saveNoteAll = async (): Promise<void> => {
    if (!note.trim()) return;
    await Promise.all(
      groupPending.map((f) =>
        resolveMut.mutateAsync({ id: f.id, resolution: note }),
      ),
    );
    setNoteMode(false);
    setNote('');
  };

  // Zebra-stripe per project group so siblings share a background block.
  const groupBg = groupIndex % 2 === 0 ? '' : 'bg-muted/15';
  const dividerCls = isGroupStart ? 'border-t-2 border-border' : 'border-t border-border/40';
  return (
    <tr className={`${dividerCls} ${groupBg} hover:bg-muted/30 align-top`}>
      <td className="px-3 py-2">
        <span className={`text-xs font-medium ${KIND_BADGE_CLASS[finding.kind]}`}>
          {DRIFT_KIND_LABELS[finding.kind] ?? finding.kind}
        </span>
      </td>
      <td className="px-3 py-2">
        {isGroupStart ? (
          finding.project_id ? (
            <Link
              to={`/tracker/projects/${finding.project_id}`}
              className="text-sm hover:underline"
              title={finding.project_code ?? undefined}
            >
              {finding.project_name ?? finding.project_id}
            </Link>
          ) : (
            <span className="text-sm text-muted-foreground">—</span>
          )
        ) : (
          <span className="text-xs text-muted-foreground">↳</span>
        )}
        {isGroupStart && finding.excel_code && (
          <div className="font-mono text-xs text-muted-foreground">{finding.excel_code}</div>
        )}
        {groupSize > 1 && (
          <div className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {groupPos} of {groupSize}
          </div>
        )}
      </td>
      <td className="px-3 py-2 max-w-md">
        <PayloadSummary payload={finding.payload} />
      </td>
      <td className="px-3 py-2 text-right whitespace-nowrap">
        {finding.resolved_at ? (
          // Resolved rows always show their own state + Reopen, regardless of
          // group membership — undo is per-finding.
          <div className="space-y-1">
            <div className="text-xs text-emerald-700">
              Resolved {new Date(finding.resolved_at).toLocaleDateString()}
            </div>
            {finding.resolution && finding.resolution !== 'Accepted' && (
              <div className="text-xs text-muted-foreground italic max-w-xs truncate" title={finding.resolution}>
                {finding.resolution}
              </div>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => reopenMut.mutate(finding.id)}
              disabled={reopenMut.isPending}
            >
              Reopen
            </Button>
          </div>
        ) : isGroup && !isGroupStart ? (
          // Continuation rows in a group: no per-row action. The group-start row
          // owns the bulk action. Render nothing (faint "↳" indicator already
          // shown in the Project column).
          <span className="text-xs text-muted-foreground">—</span>
        ) : noteMode ? (
          <div className="space-y-1">
            <Input
              autoFocus
              placeholder={isGroup ? `Note for all ${groupPending.length} findings…` : 'Add a note…'}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-64"
            />
            <div className="flex justify-end gap-1">
              <Button size="sm" variant="ghost" onClick={() => { setNoteMode(false); setNote(''); }}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={isGroup ? saveNoteAll : saveNoteOne}
                disabled={!note.trim() || resolveMut.isPending}
              >
                {resolveMut.isPending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                Save
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-end gap-2">
            <Button
              size="sm"
              onClick={isGroup ? acceptAll : acceptOne}
              disabled={resolveMut.isPending || groupPending.length === 0}
            >
              {isGroup ? `Accept all (${groupPending.length})` : 'Accept'}
            </Button>
            <button
              type="button"
              onClick={() => setNoteMode(true)}
              className="text-xs text-muted-foreground hover:underline"
            >
              + Note
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

export function DriftFindingsSection({ kinds, title, description }: DriftFindingsSectionProps): JSX.Element {
  const [includeResolved, setIncludeResolved] = useState(false);
  const { data, isLoading, error } = useDriftFindings({
    kind: kinds,
    resolved: includeResolved ? undefined : false,
  });

  return (
    <section className="space-y-3">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={includeResolved}
            onChange={(e) => setIncludeResolved(e.target.checked)}
          />
          <span>Include resolved</span>
        </label>
      </header>

      {error && <p className="text-sm text-destructive">Failed to load findings.</p>}
      {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}

      {data && data.items.length === 0 && (
        <p className="rounded border border-dashed border-muted-foreground/30 bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
          No findings to review.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Kind</th>
                <th className="px-3 py-2 text-left font-medium">Project / Excel</th>
                <th className="px-3 py-2 text-left font-medium">Detail</th>
                <th className="px-3 py-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                // Compute group-by metadata in a single pass: groupIndex
                // alternates per distinct project (drives zebra striping),
                // groupSize/groupPos drive the "1 of N" badge, and
                // groupFindings[] lets the start-row dispatch a bulk action
                // over all siblings.
                const findingsByKey: Record<string, DriftFinding[]> = {};
                data.items.forEach((f) => {
                  const key = f.project_id ?? `__no_project__${f.excel_code ?? f.id}`;
                  (findingsByKey[key] ??= []).push(f);
                });
                let groupIndex = -1;
                let prevKey: string | null = null;
                let posInGroup = 0;
                return data.items.map((f) => {
                  const key = f.project_id ?? `__no_project__${f.excel_code ?? f.id}`;
                  const isGroupStart = key !== prevKey;
                  if (isGroupStart) {
                    groupIndex += 1;
                    posInGroup = 1;
                  } else {
                    posInGroup += 1;
                  }
                  prevKey = key;
                  return (
                    <FindingRow
                      key={f.id}
                      finding={f}
                      groupIndex={groupIndex}
                      isGroupStart={isGroupStart}
                      groupSize={findingsByKey[key].length}
                      groupPos={posInGroup}
                      groupFindings={findingsByKey[key]}
                    />
                  );
                });
              })()}
            </tbody>
          </table>
          <p className="px-3 py-2 text-xs text-muted-foreground">
            {data.total} finding{data.total === 1 ? '' : 's'}
          </p>
        </div>
      )}
    </section>
  );
}
