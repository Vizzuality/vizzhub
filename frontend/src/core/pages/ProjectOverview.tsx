import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/shared/components/ui/card';
import { useProjectContext } from '@/core/contexts/ProjectContext';
import { useProjectScoresMap } from '@/modules/scorecard/hooks/useProjectScoresMap';
import { useProjectCostsMap, useProjectProgressMap } from '@/modules/tracker/public';

export default function ProjectOverview(): JSX.Element {
  const { project, projectId } = useProjectContext();
  const list = useMemo(() => [project], [project]);
  const { scoresMap } = useProjectScoresMap(list);
  const { costsMap } = useProjectCostsMap(list);
  const { progressMap } = useProjectProgressMap(list);

  const score = scoresMap[projectId] ?? null;
  const burn = costsMap[projectId]?.burn_percentage ?? null;
  const progress = progressMap[projectId]?.percentage ?? null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">Score</p>
            <p className="text-2xl font-semibold tabular-nums">
              {score === null ? '—' : Math.round(score)}
            </p>
            {project.has_scorecard && (
              <Link
                to={`/projects/${projectId}/scorecard`}
                className="text-xs text-primary hover:underline"
              >
                View scorecard →
              </Link>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">Budget burn</p>
            <p className="text-2xl font-semibold tabular-nums">
              {burn === null ? '—' : `${Math.round(burn)}%`}
            </p>
            <Link
              to={`/projects/${projectId}/tracker`}
              className="text-xs text-primary hover:underline"
            >
              View tracker →
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">Progress</p>
            <p className="text-2xl font-semibold tabular-nums">
              {progress === null ? '—' : `${Math.round(progress)}%`}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="pt-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Project details
            </p>
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{project.status}</dd>
              </div>
              {project.client_name && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Client</dt>
                  <dd className="font-medium">{project.client_name}</dd>
                </div>
              )}
              {project.program_name && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Program</dt>
                  <dd className="font-medium">{project.program_name}</dd>
                </div>
              )}
              {project.project_manager_name && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">PM</dt>
                  <dd className="font-medium">{project.project_manager_name}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Key dates
            </p>
            <dl className="space-y-1.5 text-sm">
              {project.start_date && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Start</dt>
                  <dd className="font-medium tabular-nums">{project.start_date}</dd>
                </div>
              )}
              {project.end_date && (
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">End</dt>
                  <dd className="font-medium tabular-nums">{project.end_date}</dd>
                </div>
              )}
              {!project.start_date && !project.end_date && (
                <p className="text-muted-foreground">No dates set</p>
              )}
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
