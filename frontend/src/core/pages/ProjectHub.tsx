import { Outlet, useParams } from 'react-router-dom';
import { useProject } from '@/core/hooks/useProjects';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import { ProjectHeader } from '@/core/components/ProjectHeader';
import { ProjectTabNav } from '@/core/components/layout/ProjectTabNav';

export default function ProjectHubLayout(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading } = useProject(id ?? '');

  if (isLoading) return <LoadingSpinner />;
  if (!project) {
    return <p className="text-muted-foreground text-sm py-8 text-center">Project not found.</p>;
  }

  return (
    <ProjectProvider project={project}>
      <div className="space-y-4">
        <ProjectHeader />
        <ProjectTabNav />
        <Outlet />
      </div>
    </ProjectProvider>
  );
}
