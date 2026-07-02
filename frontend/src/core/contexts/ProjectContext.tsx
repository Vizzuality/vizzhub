import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { Project } from '@/core/types/project';

interface ProjectContextValue {
  project: Project;
  projectId: string;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

interface ProjectProviderProps {
  readonly project: Project;
  readonly children: ReactNode;
}

export function ProjectProvider({ project, children }: ProjectProviderProps): JSX.Element {
  const value = useMemo(() => ({ project, projectId: project.id }), [project]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProjectContext(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (ctx === null) {
    throw new Error('useProjectContext must be used within a ProjectProvider');
  }
  return ctx;
}
