import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3 } from 'lucide-react';
import { useProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading: projectLoading, error: projectError } = useProject(id!);
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(id!);

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
        </div>
      </div>

      {scoresLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
        </div>
      )}

      {scoresError && (
        <div className="card bg-yellow-50 border-yellow-200 text-yellow-800">
          No metrics available yet. Add metrics to see the scorecard.
        </div>
      )}

      {scores && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ScoreCard score={scores.scores} />
          <DimensionChart scores={scores.scores.dimensions} />
        </div>
      )}
    </div>
  );
}
