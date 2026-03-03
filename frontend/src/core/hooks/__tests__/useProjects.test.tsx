import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  usePaginatedProjects,
  useProjectSummaries,
  useProject,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
} from '../useProjects';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';
import type { ProjectCreate, ProjectUpdate } from '@/core/types/project';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useProjects', () => {
  describe('usePaginatedProjects', () => {
    it('fetches paginated projects', async () => {
      const { result } = renderHook(() => usePaginatedProjects({ page: 1 }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toMatchObject({
        items: [expect.objectContaining({ id: 'project-123', name: 'Test Project' })],
        total: 1,
        page: 1,
        page_size: 45,
        pages: 1,
      });
    });

    it('passes search params to API', async () => {
      let capturedUrl: string | undefined;
      server.use(
        http.get('/api/scorecards', ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(fixtures.paginatedProjects);
        }),
      );

      const params = { page: 1, search: 'test', status: 'in_progress' as const };
      const { result } = renderHook(() => usePaginatedProjects(params), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const url = new URL(capturedUrl!);
      expect(url.searchParams.get('search')).toBe('test');
      expect(url.searchParams.get('status')).toBe('in_progress');
      expect(url.searchParams.get('page')).toBe('1');
    });

    it('handles API errors', async () => {
      server.use(
        http.get('/api/scorecards', () => {
          return HttpResponse.json(
            { detail: 'Internal Server Error' },
            { status: 500 },
          );
        }),
      );

      const { result } = renderHook(() => usePaginatedProjects({}), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeDefined();
    });
  });

  describe('useProjectSummaries', () => {
    it('fetches project summaries', async () => {
      const { result } = renderHook(() => useProjectSummaries(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([
        { id: 'project-123', name: 'Test Project' },
      ]);
    });
  });

  describe('useProject', () => {
    it('fetches and returns a single project', async () => {
      const { result } = renderHook(() => useProject('project-123'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toMatchObject({
        id: 'project-123',
        name: 'Test Project',
        jira_project_key: 'TEST',
        github_repo: 'org/test-repo',
      });
    });

    it('does not fetch when id is empty', () => {
      const { result } = renderHook(() => useProject(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
    });

    it('handles 404 not found', async () => {
      server.use(
        http.get('/api/scorecards/:id', () => {
          return HttpResponse.json(
            { detail: 'Project not found' },
            { status: 404 },
          );
        }),
      );

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

      let capturedBody: unknown;
      server.use(
        http.post('/api/scorecards', async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json(
            { ...fixtures.project, id: 'new-project-id', ...newProject },
            { status: 201 },
          );
        }),
      );

      const { result } = renderHook(() => useCreateProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(newProject);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toMatchObject({
        id: 'new-project-id',
        name: 'New Project',
        jira_project_key: 'NEW',
        github_repo: 'org/new-repo',
      });
      expect(capturedBody).toMatchObject(newProject);
    });

    it('handles validation errors', async () => {
      server.use(
        http.post('/api/scorecards', () => {
          return HttpResponse.json(
            { detail: 'Validation error' },
            { status: 422 },
          );
        }),
      );

      const invalidProject: ProjectCreate = {
        name: '',
        jira_project_key: '',
        github_repo: '',
      };

      const { result } = renderHook(() => useCreateProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(invalidProject);

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useUpdateProject', () => {
    it('updates an existing project', async () => {
      const projectId = 'project-123';
      const updates: ProjectUpdate = { name: 'Updated Name' };

      let capturedBody: unknown;
      server.use(
        http.patch('/api/scorecards/:id', async ({ request, params }) => {
          capturedBody = await request.json();
          return HttpResponse.json({
            ...fixtures.project,
            id: params.id,
            ...(capturedBody as Record<string, unknown>),
          });
        }),
      );

      const { result } = renderHook(() => useUpdateProject(projectId), {
        wrapper: createWrapper(),
      });

      result.current.mutate(updates);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toMatchObject({
        id: projectId,
        name: 'Updated Name',
      });
      expect(capturedBody).toMatchObject(updates);
    });

    it('partially updates project fields', async () => {
      const projectId = 'project-123';
      const updates: ProjectUpdate = { jira_project_key: 'UPDATED' };

      const { result } = renderHook(() => useUpdateProject(projectId), {
        wrapper: createWrapper(),
      });

      result.current.mutate(updates);

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.jira_project_key).toBe('UPDATED');
      expect(result.current.data?.name).toBe('Test Project');
    });
  });

  describe('useDeleteProject', () => {
    it('deletes a project', async () => {
      let capturedId: string | undefined;
      server.use(
        http.delete('/api/scorecards/:id', ({ params }) => {
          capturedId = params.id as string;
          return new HttpResponse(null, { status: 204 });
        }),
      );

      const { result } = renderHook(() => useDeleteProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('project-123');

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(capturedId).toBe('project-123');
    });

    it('handles 404 when deleting nonexistent project', async () => {
      server.use(
        http.delete('/api/scorecards/:id', () => {
          return HttpResponse.json(
            { detail: 'Not found' },
            { status: 404 },
          );
        }),
      );

      const { result } = renderHook(() => useDeleteProject(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('nonexistent');

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });
});
