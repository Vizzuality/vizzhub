import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, ChevronDown, ExternalLink } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';
import { formatDate } from '@/utils/formatters';
import { getStatusLabel } from '@/utils/projectStatus';
import { projectsApi } from '@/core/services/projects';
import StatusControls from './StatusControls';
import type { Project } from '@/core/types/project';

interface ProjectLink {
  id: string;
  title: string | null;
  url: string | null;
  link_type: string | null;
}

interface ProjectHeaderProps {
  project: Project;
}

export default function ProjectHeader({
  project,
}: ProjectHeaderProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;
  const [links, setLinks] = useState<ProjectLink[]>([]);

  useEffect(() => {
    projectsApi.getLinks(project.id).then(setLinks).catch(() => setLinks([]));
  }, [project.id]);

  return (
    <>
      <Link
        to="/scorecard"
        className="inline-flex items-center gap-2 text-base text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Scorecard
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3">
                <CardTitle className="text-3xl font-semibold">{project.name}</CardTitle>
                <Badge
                  variant={project.status === 'finished' ? 'default' : 'secondary'}
                  className={
                    project.status === 'finished'
                      ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black'
                      : ''
                  }
                >
                  {getStatusLabel(project.status)}
                </Badge>
              </div>
              {hasDateRange && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="w-4 h-4 shrink-0" />
                  {project.start_date && formatDate(project.start_date)}
                  {project.start_date && project.end_date && ' - '}
                  {project.end_date && formatDate(project.end_date)}
                </div>
              )}
              <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 text-base text-muted-foreground">
                {project.jira_project_key && (
                  <span className="flex items-center gap-2 min-w-0">
                    <BarChart3 className="w-5 h-5 shrink-0" />
                    <span className="truncate">Jira: {project.jira_project_key}</span>
                  </span>
                )}
                {project.github_repo && (
                  <span className="flex items-center gap-2 min-w-0">
                    <Github className="w-5 h-5 shrink-0" />
                    <span className="truncate">GitHub: {project.github_repo}</span>
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link to={`/projects/${project.id}/edit`}>
                <Button type="button" variant="ghost" size="sm" className="border border-input">
                  <Pencil className="w-4 h-4 mr-2" />
                  Edit
                </Button>
              </Link>
              <StatusControls projectId={project.id} />
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-0">
            <Collapsible defaultOpen>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group">
                More Info
                <ChevronDown className="w-4 h-4 transition-transform group-data-[state=closed]:-rotate-90" />
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-4 space-y-4">
                {project.summary && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Summary</p>
                    <p className="text-sm">{project.summary}</p>
                  </div>
                )}
                {project.notes && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Notes</p>
                    <p className="text-sm whitespace-pre-line">{project.notes}</p>
                  </div>
                )}
                {links.length > 0 && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Links</p>
                    <div className="flex flex-wrap gap-3">
                      {links.map((link) => (
                        <a
                          key={link.id}
                          href={link.url ?? '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          {link.title || link.url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </CollapsibleContent>
            </Collapsible>
          </CardContent>
      </Card>
    </>
  );
}
