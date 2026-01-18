import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, RefreshCw } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics } from '../hooks/useMetrics';
import { useCollectJiraMetrics } from '../hooks/useCollectors';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '../types';

function formatDate(dateString: string | null): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: project, isLoading: projectLoading, error: projectError } = useProject(id!);
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(id!);
  const { data: metrics } = useProjectMetrics(id!);
  const replaceProject = useReplaceProject(id!);
  const deleteProject = useDeleteProject();
  const collectJiraMetrics = useCollectJiraMetrics(id!);

  const handleEdit = async (data: ProjectCreate): Promise<void> => {
    await replaceProject.mutateAsync(data);
    setIsEditing(false);
  };

  const handleDelete = async (): Promise<void> => {
    await deleteProject.mutateAsync(id!);
    navigate('/projects');
  };

  const handleCollectMetrics = async (): Promise<void> => {
    await collectJiraMetrics.mutateAsync();
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="text-red-500 p-4">
        Error loading project: {projectError?.message || 'Project not found'}
      </div>
    );
  }

  const hasDateRange = project.start_date || project.end_date;

  return (
    <div>
      <Link
        to="/projects"
        className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Projects
      </Link>

      <div className="card mb-6">
        {isEditing ? (
          <>
            <h2 className="text-lg font-semibold mb-4">Edit Project</h2>
            <ProjectForm
              project={project}
              onSubmit={handleEdit}
              onCancel={() => setIsEditing(false)}
              isLoading={replaceProject.isPending}
            />
          </>
        ) : (
          <>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
                <div className="flex items-center gap-6 mt-3 text-sm text-gray-500">
                  {project.jira_project_key && (
                    <span className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4" />
                      Jira: {project.jira_project_key}
                    </span>
                  )}
                  {project.github_repo && (
                    <span className="flex items-center gap-2">
                      <Github className="w-4 h-4" />
                      GitHub: {project.github_repo}
                    </span>
                  )}
                  {hasDateRange && (
                    <span className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      {project.start_date && project.end_date
                        ? `${formatDate(project.start_date)} - ${formatDate(project.end_date)}`
                        : project.start_date
                          ? `Started ${formatDate(project.start_date)}`
                          : `Ends ${formatDate(project.end_date)}`}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {project.jira_project_key && (
                  <button
                    onClick={handleCollectMetrics}
                    disabled={collectJiraMetrics.isPending}
                    className="btn-primary flex items-center gap-2"
                  >
                    <RefreshCw className={`w-4 h-4 ${collectJiraMetrics.isPending ? 'animate-spin' : ''}`} />
                    {collectJiraMetrics.isPending ? 'Collecting...' : 'Collect Metrics'}
                  </button>
                )}
                <button
                  onClick={() => setIsEditing(true)}
                  className="btn-secondary flex items-center gap-2"
                >
                  <Pencil className="w-4 h-4" />
                  Edit
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="btn-secondary text-red-600 hover:bg-red-50 flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete Project</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete &quot;{project.name}&quot;? This action cannot be
              undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="btn-secondary"
                disabled={deleteProject.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                disabled={deleteProject.isPending}
              >
                {deleteProject.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {scoresLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      )}

      {scoresError && (
        <div className="card bg-yellow-50 border-yellow-200 text-yellow-800">
          <p className="font-medium">No metrics available yet</p>
          <p className="text-sm mt-1">
            {project.jira_project_key
              ? 'Click "Collect Metrics" to fetch data from Jira.'
              : 'Configure a Jira project key to collect metrics.'}
          </p>
        </div>
      )}

      {collectJiraMetrics.isError && (
        <div className="card bg-red-50 border-red-200 text-red-800">
          <p className="font-medium">Failed to collect metrics</p>
          <p className="text-sm mt-1">
            {collectJiraMetrics.error?.message || 'An unknown error occurred'}
          </p>
        </div>
      )}

      {collectJiraMetrics.isSuccess && (
        <div className="card bg-green-50 border-green-200 text-green-800">
          Metrics collected successfully! Scores are being calculated...
        </div>
      )}

      {scores && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <ScoreCard score={scores.scores} />
          <DimensionChart scores={scores.scores.dimensions} />
        </div>
      )}

      {metrics && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Collected Metrics</h2>
          <div className="space-y-4">
            {metrics.jira_defects && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Jira Defects</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Bugs Closed:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.bugs_closed}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Tasks Completed:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.tasks_completed}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Escaped Defects:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.escaped_defects}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Incidents:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.incidents_count}</span>
                  </div>
                  {metrics.jira_defects.mttr_hours !== null && (
                    <div>
                      <span className="text-gray-500">MTTR (hours):</span>
                      <span className="ml-2 font-medium">{metrics.jira_defects.mttr_hours}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {metrics.flow_metrics && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Flow Metrics</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Total Stories:</span>
                    <span className="ml-2 font-medium">{metrics.flow_metrics.total_stories}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Stories with Reviewer:</span>
                    <span className="ml-2 font-medium">{metrics.flow_metrics.stories_with_reviewer}</span>
                  </div>
                  {metrics.flow_metrics.lead_time_days !== null && (
                    <div>
                      <span className="text-gray-500">Lead Time (days):</span>
                      <span className="ml-2 font-medium">{metrics.flow_metrics.lead_time_days}</span>
                    </div>
                  )}
                  {metrics.flow_metrics.flow_efficiency !== null && metrics.flow_metrics.flow_efficiency !== undefined && (
                    <div>
                      <span className="text-gray-500">Flow Efficiency:</span>
                      <span className="ml-2 font-medium">{(metrics.flow_metrics.flow_efficiency * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {metrics.flow_metrics.commitment_reliability !== null && metrics.flow_metrics.commitment_reliability !== undefined && (
                    <div>
                      <span className="text-gray-500">Commitment Reliability:</span>
                      <span className="ml-2 font-medium">{(metrics.flow_metrics.commitment_reliability * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="text-xs text-gray-500 pt-2 border-t">
              <p>Period: {formatDate(metrics.period_start)} - {formatDate(metrics.period_end)}</p>
              <p>Last updated: {new Date(metrics.created_at).toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
