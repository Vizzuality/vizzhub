import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProject, useReplaceProject, useDeleteProject, useUpdateProjectStatus } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics, useUpdateEVMData, useUpdateMilestones, useUpdateGovernance, useUpdatePMSatisfaction, useUpdateTestMaturity, useUpdateArchitecture, useUpdateStrategicImpact, useUpdateClientSurvey } from '../hooks/useMetrics';
import { useCollectMetrics } from '../hooks/usePeriodCapture';
import { useConfigParameters } from '../hooks/useConfig';
import { useProjectSnapshots } from '../hooks/useSnapshots';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import type { SnapshotType, Dimension } from '../types';
import { ALL_DIMENSIONS } from '../types';
import {
  ProjectHeader,
  ProjectDialogs,
  CollectorNotifications,
  EVMSection,
  QualityMetricsGrid,
  DORASection,
  SnapshotManager,
} from '../components/ProjectDetail';
import type { ProjectCreate, EVMData, Milestone } from '../types';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showFinishDialog, setShowFinishDialog] = useState(false);
  const [dismissedSuccess, setDismissedSuccess] = useState(false);
  const [visibleDimensions, setVisibleDimensions] = useState<Set<Dimension>>(new Set(ALL_DIMENSIONS));

  const handleToggleDimension = useCallback((dimension: Dimension) => {
    setVisibleDimensions((prev) => {
      const next = new Set(prev);
      if (next.has(dimension)) {
        next.delete(dimension);
      } else {
        next.add(dimension);
      }
      return next;
    });
  }, []);

  const handleResetFilters = useCallback(() => {
    setVisibleDimensions(new Set(ALL_DIMENSIONS));
  }, []);

  const { data: project, isLoading: projectLoading, error: projectError } = useProject(id!);
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(id!);
  const { data: metrics } = useProjectMetrics(id!);
  const { data: config } = useConfigParameters();
  const snapshotType: SnapshotType = 'cumulative';
  const { data: snapshots } = useProjectSnapshots(id!, 12, snapshotType);
  const replaceProject = useReplaceProject(id!);
  const deleteProject = useDeleteProject();
  const { collectMetrics, isPending: isCollecting, error: collectError, isSuccess: collectSuccess } = useCollectMetrics(id!, {
    onSuccess: () => setDismissedSuccess(false),
  });
  const updateEVM = useUpdateEVMData(id!, metrics ?? null);
  const updateMilestones = useUpdateMilestones(id!, metrics ?? null);
  const updateGovernance = useUpdateGovernance(id!, metrics ?? null);
  const updatePMSatisfaction = useUpdatePMSatisfaction(id!, metrics ?? null);
  const updateTestMaturity = useUpdateTestMaturity(id!, metrics ?? null);
  const updateArchitecture = useUpdateArchitecture(id!, metrics ?? null);
  const updateProjectStatus = useUpdateProjectStatus(id!);
  const updateStrategicImpact = useUpdateStrategicImpact(id!, metrics ?? null);
  const updateClientSurvey = useUpdateClientSurvey(id!, metrics ?? null);

  const getTarget = (name: string): number | null => {
    const targets = config?.['Targets'];
    if (!targets) return null;
    const param = targets.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  const getConstant = (name: string): number | null => {
    const constants = config?.['Gates & Constants'];
    if (!constants) return null;
    const param = constants.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  const getWeight = (category: string, name: string): number | null => {
    const weights = config?.[category];
    if (!weights) return null;
    const param = weights.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  const handleEdit = async (data: ProjectCreate): Promise<void> => {
    await replaceProject.mutateAsync(data);
    setIsEditing(false);
  };

  const handleDelete = async (): Promise<void> => {
    await deleteProject.mutateAsync(id!);
    navigate('/projects');
  };

  const handleUpdateEVM = async (data: EVMData): Promise<void> => {
    await updateEVM.mutateAsync(data);
  };

  const handleUpdateMilestones = async (data: Milestone[]): Promise<void> => {
    await updateMilestones.mutateAsync(data);
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading project: {projectError?.message || 'Project not found'}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <ProjectHeader
        project={project}
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onCancelEdit={() => setIsEditing(false)}
        onSubmitEdit={handleEdit}
        isSubmitting={replaceProject.isPending}
        onMarkFinished={() => setShowFinishDialog(true)}
        onReopen={() => updateProjectStatus.mutateAsync('in_progress')}
        onDelete={() => setShowDeleteConfirm(true)}
        isUpdatingStatus={updateProjectStatus.isPending}
        onCollectMetrics={collectMetrics}
        isCollecting={isCollecting}
        lastCollectedAt={metrics?.created_at}
      />

      <ProjectDialogs
        projectName={project.name}
        showDeleteConfirm={showDeleteConfirm}
        onDeleteConfirmChange={setShowDeleteConfirm}
        onConfirmDelete={handleDelete}
        showFinishDialog={showFinishDialog}
        onFinishDialogChange={setShowFinishDialog}
        onConfirmFinish={() => updateProjectStatus.mutateAsync('finished')}
      />

      <CollectorNotifications
        error={collectError}
        isSuccess={collectSuccess}
        dismissedSuccess={dismissedSuccess}
        onDismissSuccess={() => setDismissedSuccess(true)}
      />

      <SnapshotManager projectId={id!} />

      {scoresLoading && (
        <>
          <Separator className="my-6" />
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        </>
      )}

      {scoresError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-yellow/10 border-score-yellow/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-yellow">No metrics available yet</p>
              <p className="text-sm mt-1 text-score-yellow/80">
                {project.jira_project_key
                  ? 'Click "Collect Metrics" to fetch data from Jira.'
                  : 'Configure a Jira project key to collect metrics.'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {scores && (
        <>
          <Separator className="my-6" />
          <div>
            <h2 className="text-2xl font-semibold mb-4">Scores</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ScoreCard
                score={scores.scores}
                snapshots={snapshots}
                visibleDimensions={visibleDimensions}
                onToggleDimension={handleToggleDimension}
                onResetFilters={handleResetFilters}
              />
              <DimensionChart
                scores={scores.scores.dimensions}
                snapshots={snapshots}
                visibleDimensions={visibleDimensions}
                onToggleDimension={handleToggleDimension}
              />
            </div>
          </div>

          <EVMSection
            evmData={metrics?.evm_data}
            milestones={metrics?.milestones}
            indicators={scores.indicators}
            onUpdateEVM={handleUpdateEVM}
            onUpdateMilestones={handleUpdateMilestones}
            isUpdatingEVM={updateEVM.isPending}
            isUpdatingMilestones={updateMilestones.isPending}
            getTarget={getTarget}
            getConstant={getConstant}
            snapshots={snapshots}
            visibleDimensions={visibleDimensions}
          />
        </>
      )}

      {scores && metrics && (
        <QualityMetricsGrid
          metrics={metrics}
          indicators={scores.indicators}
          project={project}
          getTarget={getTarget}
          getWeight={getWeight}
          onUpdateGovernance={(value) => updateGovernance.mutateAsync(value)}
          onUpdatePMSatisfaction={(data) => updatePMSatisfaction.mutateAsync(data)}
          onUpdateStrategicImpact={(value) => updateStrategicImpact.mutateAsync(value)}
          onUpdateTestMaturity={(data) => updateTestMaturity.mutateAsync(data)}
          onUpdateArchitecture={(data) => updateArchitecture.mutateAsync(data)}
          onUpdateClientSurvey={(data) => updateClientSurvey.mutateAsync(data)}
          isUpdatingGovernance={updateGovernance.isPending}
          isUpdatingPMSatisfaction={updatePMSatisfaction.isPending}
          isUpdatingStrategicImpact={updateStrategicImpact.isPending}
          isUpdatingTestMaturity={updateTestMaturity.isPending}
          isUpdatingArchitecture={updateArchitecture.isPending}
          isUpdatingClientSurvey={updateClientSurvey.isPending}
          snapshots={snapshots}
          visibleDimensions={visibleDimensions}
        />
      )}

      {scores && metrics && (
        <DORASection
          scores={scores.scores}
          metrics={metrics}
          indicators={scores.indicators}
          getTarget={getTarget}
          snapshots={snapshots}
          visibleDimensions={visibleDimensions}
        />
      )}
    </div>
  );
}
