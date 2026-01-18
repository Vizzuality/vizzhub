import { Link } from 'react-router-dom';
import { ChevronRight, Github, BarChart3, Calendar } from 'lucide-react';
import type { Project } from '../../types';

interface ProjectCardProps {
  project: Project;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function ProjectCard({ project }: ProjectCardProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  return (
    <Link
      to={`/projects/${project.id}`}
      className="card hover:shadow-md transition-shadow duration-200 flex items-center justify-between"
    >
      <div className="flex-1">
        <h3 className="font-semibold text-gray-900">{project.name}</h3>
        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
          {project.jira_project_key && (
            <span className="flex items-center gap-1">
              <BarChart3 className="w-4 h-4" />
              {project.jira_project_key}
            </span>
          )}
          {project.github_repo && (
            <span className="flex items-center gap-1">
              <Github className="w-4 h-4" />
              {project.github_repo}
            </span>
          )}
          {hasDateRange && (
            <span className="flex items-center gap-1">
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
      <ChevronRight className="w-5 h-5 text-gray-400" />
    </Link>
  );
}
