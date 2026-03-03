import { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useProject, useReplaceProject, useDeleteProject, useUpdateProjectStatus } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics, useUpdateEVMData, useUpdateMilestones, useUpdateGovernance, useUpdatePMSatisfaction, useUpdateTestMaturity, useUpdateArchitecture, useUpdateStrategicImpact, useUpdateClientSurvey } from '../hooks/useMetrics';
import { useCapturePeriod } from '../hooks/usePeriodCapture';
import { useConfigParameters } from '../hooks/useConfig';
import { useProjectSnapshots } from '../hooks/useSnapshots';
import { getMonthsSinceStart, MONTH_NAMES } from '../utils/dateUtils';
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
  InteractiveTimelineChart,
  EmptyPeriodOverlay,
} from '../components/ProjectDetail';
import type { ProjectCreate, EVMData, Milestone } from '../types';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Separator } from '@/shared/components/ui/separator';
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
} from '@/shared/components/ui/alert-dialog';

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showFinishDialog, setShowFinishDialog] = useState(false);
  const [dismissedSuccess, setDismissedSuccess] = useState(false);
  const [visibleDimensions, setVisibleDimensions] = useState<Set<Dimension>>(new Set(ALL_DIMENSIONS));
  const periodSchema = useMemo(() => ({
    year: { defaultValue: 0 },
    month: { defaultValue: 0 },
  }), []);
  const { state: periodState, setState: setPeriodState } = useUrlState(periodSchema);
  const selectedPeriod = periodState.year && periodState.month
    ? { year: periodState.year, month: periodState.month }
    : null;
  const setSelectedPeriod = useCallback(
    (period: { year: number; month: number } | null) => {
      setPeriodState(
        { year: period?.year ?? 0, month: period?.month ?? 0 },
        { replace: false },
      );
    },
    [setPeriodState],
  );
  const [showHistoricalWarning, setShowHistoricalWarning] = useState(false);
  const [pendingUpdate, setPendingUpdate] = useState<(() => Promise<void>) | null>(null);

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
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(
    id!,
    selectedPeriod?.year,
    selectedPeriod?.month,
  );
  const { data: metrics } = useProjectMetrics(
    id!,
    selectedPeriod?.year,
    selectedPeriod?.month,
  );
  const { data: config } = useConfigParameters();
  const snapshotType: SnapshotType = 'cumulative';
  const snapshotLimit = useMemo(
    () => getMonthsSinceStart(project?.start_date),
    [project?.start_date],
  );
  const { data: snapshots } = useProjectSnapshots(id!, snapshotLimit, snapshotType);
  const replaceProject = useReplaceProject(id!);
  const deleteProject = useDeleteProject();
  const updateEVM = useUpdateEVMData(id!, metrics ?? null, selectedPeriod);
  const updateMilestones = useUpdateMilestones(id!, metrics ?? null, selectedPeriod);
  const updateGovernance = useUpdateGovernance(id!, metrics ?? null, selectedPeriod);
  const updatePMSatisfaction = useUpdatePMSatisfaction(id!, metrics ?? null, selectedPeriod);
  const updateTestMaturity = useUpdateTestMaturity(id!, metrics ?? null, selectedPeriod);
  const updateArchitecture = useUpdateArchitecture(id!, metrics ?? null, selectedPeriod);
  const updateProjectStatus = useUpdateProjectStatus(id!);
  const updateStrategicImpact = useUpdateStrategicImpact(id!, metrics ?? null, selectedPeriod);
  const updateClientSurvey = useUpdateClientSurvey(id!, metrics ?? null, selectedPeriod);
  const {
    mutateAsync: capturePeriod,
    isPending: isPeriodCapturing,
    error: periodCaptureError,
    isSuccess: captureSuccess,
    reset: resetCaptureState,
  } = useCapturePeriod(id!);

  const getTarget = (name: string): number | null => {
    const targets = config?.['Targets'];
    if (!targets) return null;
    const param = targets.find((p) => p.name === name);
    return param ? Number.parseFloat(param.value) : null;
  };

  const getConstant = (name: string): number | null => {
    const constants = config?.['Gates & Constants'];
    if (!constants) return null;
    const param = constants.find((p) => p.name === name);
    return param ? Number.parseFloat(param.value) : null;
  };

  const getWeight = (category: string, name: string): number | null => {
    const weights = config?.[category];
    if (!weights) return null;
    const param = weights.find((p) => p.name === name);
    return param ? Number.parseFloat(param.value) : null;
  };

  const handleEdit = async (data: ProjectCreate): Promise<void> => {
    await replaceProject.mutateAsync(data);
    setIsEditing(false);
  };

  const handleDelete = async (): Promise<void> => {
    await deleteProject.mutateAsync(id!);
    navigate('/scorecard');
  };

  const handleUpdateEVM = async (data: EVMData): Promise<void> => {
    await withHistoricalWarning(() => updateEVM.mutateAsync(data))();
  };

  const handleUpdateMilestones = async (data: Milestone[]): Promise<void> => {
    await withHistoricalWarning(() => updateMilestones.mutateAsync(data))();
  };

  const handleCapturePeriod = async (): Promise<void> => {
    if (!selectedPeriod) return;
    await capturePeriod({
      year: selectedPeriod.year,
      month: selectedPeriod.month,
      force: false,
    });
  };

  const periodHasData = useMemo(() => {
    if (!selectedPeriod || !snapshots) return true;
    return snapshots.some(
      (s) => s.period_year === selectedPeriod.year && s.period_month === selectedPeriod.month,
    );
  }, [selectedPeriod, snapshots]);

  const isHistoricalPeriod = useMemo(() => {
    if (!selectedPeriod) return false;
    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth() + 1;
    return (
      selectedPeriod.year < currentYear ||
      (selectedPeriod.year === currentYear && selectedPeriod.month < currentMonth)
    );
  }, [selectedPeriod]);

  const withHistoricalWarning = useCallback(
    <T,>(updateFn: () => Promise<T>): (() => Promise<T | void>) => {
      return async () => {
        if (isHistoricalPeriod) {
          setPendingUpdate(() => updateFn as () => Promise<void>);
          setShowHistoricalWarning(true);
          return;
        }
        return updateFn();
      };
    },
    [isHistoricalPeriod],
  );

  const handleConfirmHistoricalUpdate = useCallback(async () => {
    setShowHistoricalWarning(false);
    if (pendingUpdate) {
      await pendingUpdate();
      setPendingUpdate(null);
    }
  }, [pendingUpdate]);

  if (projectLoading) {
    return <LoadingSpinner />;
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
        onReopen={() => updateProjectStatus.mutateAsync({ status: 'in_progress' })}
        onDelete={() => setShowDeleteConfirm(true)}
        isUpdatingStatus={updateProjectStatus.isPending}
      />

      <ProjectDialogs
        projectName={project.name}
        showDeleteConfirm={showDeleteConfirm}
        onDeleteConfirmChange={setShowDeleteConfirm}
        onConfirmDelete={handleDelete}
        showFinishDialog={showFinishDialog}
        onFinishDialogChange={setShowFinishDialog}
        onConfirmFinish={(finishedAt: string) =>
          updateProjectStatus.mutateAsync({ status: 'finished', finished_at: finishedAt })
        }
      />

      {/* Historical Period Update Warning */}
      <AlertDialog open={showHistoricalWarning} onOpenChange={setShowHistoricalWarning}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Update historical data?</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to modify metrics for{' '}
              <strong>
                {selectedPeriod
                  ? `${MONTH_NAMES[selectedPeriod.month - 1]} ${selectedPeriod.year}`
                  : 'this period'}
              </strong>. This is a past period and changes may affect historical reports.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingUpdate(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmHistoricalUpdate}>
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <SnapshotManager projectId={id!} projectName={project?.name ?? ''} />

      {project.start_date && (
        <>
          <Separator className="my-6" />
          <InteractiveTimelineChart
            projectStartDate={project.start_date}
            projectFinishedAt={project.finished_at}
            snapshots={snapshots}
            selectedPeriod={selectedPeriod}
            onPeriodChange={setSelectedPeriod}
            isCapturing={isPeriodCapturing}
            onCollectMetrics={async (period, force) => {
              await capturePeriod({ year: period.year, month: period.month, force });
            }}
            isCollecting={isPeriodCapturing}
            hasCollectors={!!(project.jira_project_key || project.github_repo)}
            isFinished={project.status === 'finished'}
          />

          <CollectorNotifications
            error={periodCaptureError}
            isSuccess={captureSuccess}
            dismissedSuccess={dismissedSuccess}
            onDismissSuccess={() => {
              setDismissedSuccess(true);
              resetCaptureState();
            }}
          />
        </>
      )}

      {scoresLoading && (
        <LoadingSpinner className="h-32" />
      )}

      {scoresError && !scoresLoading && (
        <Card className="bg-score-yellow/10 border-score-yellow/30">
          <CardContent className="pt-6">
            <p className="font-medium text-score-yellow">No metrics available yet</p>
            <p className="text-sm mt-1 text-score-yellow/80">
              {project.jira_project_key
                ? 'Click "Collect Metrics" above to fetch data from Jira.'
                : 'Configure a Jira project key to collect metrics.'}
            </p>
          </CardContent>
        </Card>
      )}

      {scores && (
        <>
          <div>
            <div className="relative">
              {selectedPeriod && !periodHasData && (
                <EmptyPeriodOverlay
                  period={selectedPeriod}
                  onCapture={handleCapturePeriod}
                  isCapturing={isPeriodCapturing}
                  error={periodCaptureError}
                />
              )}

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
          onUpdateGovernance={(value) => withHistoricalWarning(() => updateGovernance.mutateAsync(value))()}
          onUpdatePMSatisfaction={(data) => withHistoricalWarning(() => updatePMSatisfaction.mutateAsync(data))()}
          onUpdateStrategicImpact={(value) => withHistoricalWarning(() => updateStrategicImpact.mutateAsync(value))()}
          onUpdateTestMaturity={(data) => withHistoricalWarning(() => updateTestMaturity.mutateAsync(data))()}
          onUpdateArchitecture={(data) => withHistoricalWarning(() => updateArchitecture.mutateAsync(data))()}
          onUpdateClientSurvey={(data) => withHistoricalWarning(() => updateClientSurvey.mutateAsync(data))()}
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
