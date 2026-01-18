import { useState } from 'react';
import { Plus } from 'lucide-react';
import { useProjects, useCreateProject } from '../hooks/useProjects';
import ProjectCard from '../components/Dashboard/ProjectCard';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '../types';

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 p-4">
        Error loading projects: {error.message}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <button
          onClick={() => setShowForm(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Create Project
        </button>
      </div>

      {showForm && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold mb-4">Create New Project</h2>
          <ProjectForm
            onSubmit={handleCreate}
            onCancel={() => setShowForm(false)}
            isLoading={createProject.isPending}
          />
        </div>
      )}

      {projects && projects.length > 0 ? (
        <div className="grid gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <p className="text-gray-500 mb-4">No projects yet</p>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            Create your first project
          </button>
        </div>
      )}
    </div>
  );
}
