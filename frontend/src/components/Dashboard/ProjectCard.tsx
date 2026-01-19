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
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{project.name}</CardTitle>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 text-base text-muted-foreground">
          {project.jira_project_key && (
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              <span>Jira: {project.jira_project_key}</span>
            </div>
          )}
          {project.github_repo && (
            <div className="flex items-center gap-2">
              <Github className="w-5 h-5" />
              <span>GitHub: {project.github_repo}</span>
            </div>
          )}
          {hasDateRange && (
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              <span>
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            </div>
          )}
        </div>
      </CardContent>

      <CardFooter>
        <Link
          to={`/projects/${project.id}`}
          className="text-base font-medium text-primary hover:underline"
        >
          View Details →
        </Link>
      </CardFooter>
    </Card>
  );
}
