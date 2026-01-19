import { Link } from 'react-router-dom';
import { BarChart3, Github, Calendar } from 'lucide-react';
import type { Project } from '../../types';
import { formatDate } from '../../utils/formatters';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface ProjectCardProps {
  project: Project;
}

export default function ProjectCard({ project }: ProjectCardProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6">
        <div className="flex-1 space-y-3">
          <CardTitle className="text-xl font-semibold">{project.name}</CardTitle>
          <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 text-base text-muted-foreground">
            {project.jira_project_key && (
              <span className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Jira: {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-2">
                <Github className="w-5 h-5" />
                GitHub: {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            )}
          </div>
        </div>

        <div className="md:flex-shrink-0">
          <Link
            to={`/projects/${project.id}`}
            className="text-base font-medium text-primary hover:underline"
          >
            View Details →
          </Link>
        </div>
      </div>
    </Card>
  );
}
