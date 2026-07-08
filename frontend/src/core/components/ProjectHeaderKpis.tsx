import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { usePermission, Action } from '@/core/permissions';
import { useProjectContext } from '@/core/contexts/ProjectContext';
import { useProjectScoresMap } from '@/modules/scorecard/hooks/useProjectScoresMap';
import { useProjectCostsMap, useProjectProgressMap } from '@/modules/tracker/public';
import { getBurnDotClass, getScoreDotClass } from '@/utils/scoreColors';

const SCORE_THRESHOLDS = { green: 70, yellow: 40 };

function Kpi({
  label,
  value,
  dotClass,
}: {
  readonly label: string;
  readonly value: string;
  readonly dotClass?: string;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground leading-none mb-1">
        {label}
      </div>
      <div className="flex items-center gap-1.5">
        {dotClass && <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', dotClass)} />}
        <span className="text-sm font-medium leading-tight tabular-nums">{value}</span>
      </div>
    </div>
  );
}

/** Compact Score / Burn / Progress strip shown in the project hub header. */
export function ProjectHeaderKpis(): JSX.Element | null {
  const { project, projectId } = useProjectContext();
  const canTracker = usePermission(Action.TRACKER_VIEW);
  const list = useMemo(() => [project], [project]);
  const { scoresMap } = useProjectScoresMap(list);
  const { costsMap } = useProjectCostsMap(list);
  const { progressMap } = useProjectProgressMap(list);

  const score = scoresMap[projectId] ?? null;
  const burn = costsMap[projectId]?.burn_percentage ?? null;
  const progress = progressMap[projectId]?.percentage ?? null;

  if (!project.has_scorecard && !canTracker) return null;

  return (
    <div className="flex items-end gap-5">
      {project.has_scorecard && (
        <Kpi
          label="Score"
          value={score === null ? '—' : String(Math.round(score))}
          dotClass={getScoreDotClass(score, SCORE_THRESHOLDS)}
        />
      )}
      {canTracker && (
        <>
          <Kpi
            label="Burn"
            value={burn === null ? '—' : `${Math.round(burn)}%`}
            dotClass={getBurnDotClass(burn)}
          />
          <Kpi
            label="Progress"
            value={progress === null ? '—' : `${Math.round(progress)}%`}
          />
        </>
      )}
    </div>
  );
}
