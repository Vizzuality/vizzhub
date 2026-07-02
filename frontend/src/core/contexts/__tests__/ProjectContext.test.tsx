import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { ProjectProvider, useProjectContext } from '../ProjectContext';
import type { Project } from '@/core/types/project';

const project = { id: 'p1', name: 'Ocean Watch' } as Project;

describe('ProjectContext', () => {
  it('provides the project to consumers', () => {
    const { result } = renderHook(() => useProjectContext(), {
      wrapper: ({ children }) => <ProjectProvider project={project}>{children}</ProjectProvider>,
    });
    expect(result.current.project.name).toBe('Ocean Watch');
    expect(result.current.projectId).toBe('p1');
  });

  it('throws outside a provider', () => {
    expect(() => renderHook(() => useProjectContext())).toThrow();
  });
});
