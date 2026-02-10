import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  usePaginatedProjects,
  useProjectSummaries,
  useProject,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
} from '../useProjects';
import { projectsApi } from '../../services/api';
import type {
  PaginatedProjects,
  Project,
  ProjectCreate,
  ProjectSummary,
  ProjectUpdate,
} from '../../types';

vi.mock('../../services/api', () => ({
  projectsApi: {
    list: vi.fn(),
    listSummary: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    replace: vi.fn(),
    delete: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useProjects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('usePaginatedProjects', () => {
    it('fetches paginated projects', async () => {
      const mockResponse: PaginatedProjects = {
        items: [
          {
            id: '1',
            name: 'Project 1',
            jira_project_key: 'PROJ1',
            github_repo: 'org/repo1',
            created_at: '2026-01-01',
            updated_at: '2026-01-01',
          } as Project,
        ],
        total: 1,
        page: 1,
        page_size: 45,
        pages: 1,
      };

      vi.mocked(projectsApi.list).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => usePaginatedProjects({ page: 1 }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(projectsApi.list).toHaveBeenCalledWith({ page: 1 });
    });

    it('passes search params to API', async () => {
      const mockResponse: PaginatedProjects = {
        items: [],
        total: 0,
        page: 1,
        page_size: 45,
        pages: 1,
      };

      vi.mocked(projectsApi.list).mockResolvedValue(mockResponse);

      const params = { page: 1, search: 'test', status: 'in_progress' };
      const { result } = renderHook(() => usePaginatedProjects(params), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(projectsApi.list).toHaveBeenCalledWith(params);
    });

    it('handles API errors', async () => {
      vi.mocked(projectsApi.list).mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => usePaginatedProjects({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useProjectSummaries', () => {
    it('fetches project summaries', async () => {
      const mockSummaries: ProjectSummary[] = [
        { id: '1', name: 'Alpha' },
        { id: '2', name: 'Beta' },
      ];

      vi.mocked(projectsApi.listSummary).mockResolvedValue(mockSummaries);

      const { result } = renderHook(() => useProjectSummaries(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockSummaries);
      expect(projectsApi.listSummary).toHaveBeenCalledTimes(1);
    });
  });

  describe('useProject', () => {
    it('fetches and returns a single project', async () => {
      const mockProject: Project = {
        id: '1',
        name: 'Test Project',
        jira_project_key: 'TEST',
        github_repo: 'org/repo',
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      } as Project;

      vi.mocked(projectsApi.get).mockResolvedValue(mockProject);

      const { result } = renderHook(() => useProject('1'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockProject);
      expect(projectsApi.get).toHaveBeenCalledWith('1');
    });

    it('does not fetch when id is empty', () => {
      const { result } = renderHook(() => useProject(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
      expect(projectsApi.get).not.toHaveBeenCalled();
    });

    it('handles 404 not found', async () => {
      vi.mocked(projectsApi.get).mockRejectedValue({ response: { status: 404 } });

      const { result } = renderHook(() => useProject('nonexistent'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useCreateProject', () => {
    it('creates a new project', async () => {
      const newProject: ProjectCreate = {
        name: 'New Project',
        jira_project_key: 'NEW',
        github_repo: 'org/new-repo',
      };

      const createdProject: Project = {
        id: '123',
        ...newProject,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      } as Project;

      vi.mocked(projectsApi.create).mockResolvedValue(createdProject);

      const { result } = renderHook(() => useCreateProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(newProject);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(createdProject);
      expect(projectsApi.create).toHaveBeenCalledWith(newProject);
    });

    it('handles validation errors', async () => {
      const invalidProject: ProjectCreate = {
        name: '',
        jira_project_key: '',
        github_repo: '',
      };

      vi.mocked(projectsApi.create).mockRejectedValue({
        response: {
          status: 422,
          data: { detail: 'Validation error' },
        },
      });

      const { result } = renderHook(() => useCreateProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(invalidProject);

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useUpdateProject', () => {
    it('updates an existing project', async () => {
      const projectId = '123';
      const updates: ProjectUpdate = {
        name: 'Updated Name',
      };

      const updatedProject: Project = {
        id: projectId,
        name: 'Updated Name',
        jira_project_key: 'TEST',
        github_repo: 'org/repo',
        created_at: '2026-01-01',
        updated_at: '2026-01-02',
      } as Project;

      vi.mocked(projectsApi.update).mockResolvedValue(updatedProject);

      const { result } = renderHook(() => useUpdateProject(projectId), {
        wrapper: createWrapper(),
      });

      result.current.mutate(updates);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(updatedProject);
      expect(projectsApi.update).toHaveBeenCalledWith(projectId, updates);
    });

    it('partially updates project fields', async () => {
      const projectId = '123';
      const updates: ProjectUpdate = {
        jira_project_key: 'UPDATED',
      };

      const updatedProject: Project = {
        id: projectId,
        name: 'Original Name',
        jira_project_key: 'UPDATED',
        github_repo: 'org/repo',
        created_at: '2026-01-01',
        updated_at: '2026-01-02',
      } as Project;

      vi.mocked(projectsApi.update).mockResolvedValue(updatedProject);

      const { result } = renderHook(() => useUpdateProject(projectId), {
        wrapper: createWrapper(),
      });

      result.current.mutate(updates);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.jira_project_key).toBe('UPDATED');
      expect(result.current.data?.name).toBe('Original Name');
    });
  });

  describe('useDeleteProject', () => {
    it('deletes a project', async () => {
      const projectId = '123';

      vi.mocked(projectsApi.delete).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(projectId);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(projectsApi.delete).toHaveBeenCalledWith(projectId);
    });

    it('handles 404 when deleting nonexistent project', async () => {
      vi.mocked(projectsApi.delete).mockRejectedValue({
        response: { status: 404 },
      });

      const { result } = renderHook(() => useDeleteProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });
});
