import { useParams, Link } from 'react-router-dom';
import { useProject } from '../hooks/useProjects';
import { useProjectSnapshots } from '../hooks/useSnapshots';
import { TrendChart } from '../components/TrendChart';
import SnapshotManager from '../components/ProjectDetail/SnapshotManager';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Calendar, TrendingUp, Loader2 } from 'lucide-react';
import type { DimensionScores } from '../types';

export default function ProjectHistory(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading: projectLoading } = useProject(id!);
  const { data: snapshots, isLoading: snapshotsLoading } = useProjectSnapshots(id!);

  if (projectLoading || snapshotsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-muted-foreground">Project not found.</p>
            <Button asChild className="mt-4">
              <Link to="/">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Projects
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const dimensionKeys: (keyof DimensionScores)[] = [
    'p_time', 'p_cost', 'p_quality', 'p_value',
    'p_satisfaction', 'p_flow', 'p_engineering', 'p_risk',
  ];

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{project.name}</h1>
          <p className="text-muted-foreground mt-1">Historical Score Trends</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/projects/${id}`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Link>
        </Button>
      </div>

      <SnapshotManager projectId={id!} />

      {snapshots && snapshots.length > 0 ? (
        <>
          <TrendChart
            snapshots={snapshots}
            dimensions={['final_score']}
            title="Final Score Trend"
          />

          <TrendChart
            snapshots={snapshots}
            dimensions={dimensionKeys}
            title="Dimension Breakdown"
          />

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Snapshot History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-2">Period</th>
                      <th className="text-right py-3 px-2">Final Score</th>
                      <th className="text-right py-3 px-2">Time</th>
                      <th className="text-right py-3 px-2">Cost</th>
                      <th className="text-right py-3 px-2">Quality</th>
                      <th className="text-right py-3 px-2">Flow</th>
                      <th className="text-right py-3 px-2">Engineering</th>
                      <th className="text-right py-3 px-2">Risk</th>
                      <th className="text-left py-3 px-2">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshots.map((snapshot) => (
                      <tr key={snapshot.id} className="border-b hover:bg-muted/50">
                        <td className="py-3 px-2 font-medium">
                          {snapshot.period_year}-{String(snapshot.period_month).padStart(2, '0')}
                        </td>
                        <td className="py-3 px-2 text-right font-semibold">
                          {snapshot.scores.score}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_time ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_cost ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_quality ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_flow ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_engineering ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-right">
                          {snapshot.scores.dimensions.p_risk ?? '-'}
                        </td>
                        <td className="py-3 px-2 text-muted-foreground">
                          {new Date(snapshot.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <TrendingUp className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No Snapshots Yet</p>
            <p className="text-muted-foreground mt-2">
              Create a monthly snapshot above to start tracking historical trends.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
