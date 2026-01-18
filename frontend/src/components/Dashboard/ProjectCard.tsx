import { Link } from 'react-router-dom';
import { ChevronRight, Github, BarChart3 } from 'lucide-react';
import type { Project } from '../../types';

interface ProjectCardProps {
  project: Project;
}

export default function ProjectCard({ project }: ProjectCardProps): JSX.Element {
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
        </div>
      </div>
      <ChevronRight className="w-5 h-5 text-gray-400" />
    </Link>
  );
}
