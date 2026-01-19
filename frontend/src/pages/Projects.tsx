import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useProjects, useCreateProject } from '../hooks/useProjects';
import ProjectCard from '../components/Dashboard/ProjectCard';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '../types';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function Projects(): JSX.Element {
  const [showForm, setShowForm] = useState(false);
  const { data: projects, isLoading, error } = useProjects();
  const createProject = useCreateProject();

  const handleCreate = async (data: ProjectCreate): Promise<void> => {
    await createProject.mutateAsync(data);
    setShowForm(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">Error loading projects: {error.message}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="w-5 h-5 mr-2" />
          Create Project
        </Button>
      </div>

      {/* Create Form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Project</CardTitle>
          </CardHeader>
          <CardContent>
            <ProjectForm
              onSubmit={handleCreate}
              onCancel={() => setShowForm(false)}
              isLoading={createProject.isPending}
            />
          </CardContent>
        </Card>
      )}

      {/* Projects List */}
      {projects && projects.length > 0 ? (
        <div className="grid gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground mb-4">No projects yet</p>
            <Button onClick={() => setShowForm(true)}>
              Create your first project
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
