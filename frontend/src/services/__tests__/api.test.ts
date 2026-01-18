import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import api, { projectsApi, scoresApi, configApi, collectApi } from '../api';
import type { Project, ProjectCreate, MetricsCreate } from '../../types';

describe('API Service', () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    mock.restore();
  });

  describe('Request Interceptor', () => {
    it('test_api_request_interceptor_adds_bearer_token', async () => {
      localStorage.setItem('auth_token', 'test-jwt-token');

      mock.onGet('/projects').reply((config) => {
        expect(config.headers?.Authorization).toBe('Bearer test-jwt-token');
        return [200, []];
      });

      await projectsApi.list();
    });

    it('test_api_request_interceptor_no_header_when_no_token', async () => {
      localStorage.removeItem('auth_token');

      mock.onGet('/projects').reply((config) => {
        expect(config.headers?.Authorization).toBeUndefined();
        return [200, []];
      });

      await projectsApi.list();
    });

    it('test_api_request_interceptor_uses_correct_token_format', async () => {
      const testToken = 'my-secure-jwt-token-12345';
      localStorage.setItem('auth_token', testToken);

      mock.onGet('/projects').reply((config) => {
        const authHeader = config.headers?.Authorization;
        expect(authHeader).toBe(`Bearer ${testToken}`);
        expect(authHeader).toMatch(/^Bearer .+/);
        return [200, []];
      });

      await projectsApi.list();
    });
  });

  describe('Response Interceptor', () => {
    it('test_api_response_interceptor_401_clears_token', async () => {
      localStorage.setItem('auth_token', 'expired-token');
      localStorage.setItem('auth_user', JSON.stringify({ id: '123' }));

      mock.onGet('/projects').reply(401);

      // Mock window.location.href
      delete (window as any).location;
      (window as any).location = { href: '' };

      try {
        await projectsApi.list();
      } catch (error) {
        // Expected to throw
      }

      expect(localStorage.getItem('auth_token')).toBeNull();
    });

    it('test_api_response_interceptor_401_redirects_to_login', async () => {
      localStorage.setItem('auth_token', 'expired-token');

      mock.onGet('/projects').reply(401);

      // Mock window.location
      delete (window as any).location;
      (window as any).location = { href: '' };

      try {
        await projectsApi.list();
      } catch (error) {
        // Expected to throw
      }

      expect((window as any).location.href).toBe('/login');
    });

    it('test_api_response_interceptor_401_clears_user_data', async () => {
      localStorage.setItem('auth_token', 'expired-token');
      localStorage.setItem('auth_user', JSON.stringify({ id: '123', email: 'test@example.com' }));

      mock.onGet('/projects').reply(401);

      // Mock window.location
      delete (window as any).location;
      (window as any).location = { href: '' };

      try {
        await projectsApi.list();
      } catch (error) {
        // Expected to throw
      }

      expect(localStorage.getItem('auth_user')).toBeNull();
    });

    it('test_api_response_interceptor_success_passes_through', async () => {
      const mockProjects: Project[] = [
        {
          id: '123',
          name: 'Test Project',
          jira_project_key: 'TEST',
          github_repo: 'org/repo',
          start_date: null,
          end_date: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ];

      mock.onGet('/projects').reply(200, mockProjects);

      const result = await projectsApi.list();

      expect(result).toEqual(mockProjects);
      expect(result).toHaveLength(1);
    });

    it('test_api_response_interceptor_403_not_intercepted', async () => {
      localStorage.setItem('auth_token', 'valid-token');

      mock.onGet('/projects').reply(403);

      // Mock window.location
      delete (window as any).location;
      (window as any).location = { href: '' };

      try {
        await projectsApi.list();
        expect.fail('Should have thrown error');
      } catch (error) {
        // 403 should not clear token or redirect
        expect(localStorage.getItem('auth_token')).toBe('valid-token');
        expect((window as any).location.href).toBe('');
      }
    });

    it('test_api_response_interceptor_500_not_intercepted', async () => {
      localStorage.setItem('auth_token', 'valid-token');

      mock.onGet('/projects').reply(500);

      // Mock window.location
      delete (window as any).location;
      (window as any).location = { href: '' };

      try {
        await projectsApi.list();
        expect.fail('Should have thrown error');
      } catch (error) {
        // 500 should not clear token or redirect
        expect(localStorage.getItem('auth_token')).toBe('valid-token');
        expect((window as any).location.href).toBe('');
      }
    });
  });

  describe('Projects API Methods', () => {
    it('test_projects_api_list_calls_correct_endpoint', async () => {
      mock.onGet('/projects').reply(200, []);

      await projectsApi.list();

      expect(mock.history.get).toHaveLength(1);
      expect(mock.history.get[0].url).toBe('/projects');
    });

    it('test_projects_api_get_calls_with_id', async () => {
      const projectId = '123e4567-e89b-12d3-a456-426614174000';
      const mockProject: Project = {
        id: projectId,
        name: 'Test Project',
        jira_project_key: 'TEST',
        github_repo: null,
        start_date: null,
        end_date: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      mock.onGet(`/projects/${projectId}`).reply(200, mockProject);

      const result = await projectsApi.get(projectId);

      expect(result.id).toBe(projectId);
      expect(mock.history.get[0].url).toBe(`/projects/${projectId}`);
    });

    it('test_projects_api_create_posts_data', async () => {
      const newProject: ProjectCreate = {
        name: 'New Project',
        jira_project_key: 'NEW',
        github_repo: 'org/new',
      };

      mock.onPost('/projects').reply(201, { ...newProject, id: '123' });

      await projectsApi.create(newProject);

      expect(mock.history.post).toHaveLength(1);
      expect(mock.history.post[0].url).toBe('/projects');
      expect(JSON.parse(mock.history.post[0].data)).toEqual(newProject);
    });

    it('test_projects_api_update_patches_data', async () => {
      const projectId = '123';
      const updates = { name: 'Updated Name' };

      mock.onPatch(`/projects/${projectId}`).reply(200, { id: projectId, ...updates });

      await projectsApi.update(projectId, updates);

      expect(mock.history.patch).toHaveLength(1);
      expect(mock.history.patch[0].url).toBe(`/projects/${projectId}`);
      expect(JSON.parse(mock.history.patch[0].data)).toEqual(updates);
    });

    it('test_projects_api_replace_puts_data', async () => {
      const projectId = '123';
      const replacement: ProjectCreate = {
        name: 'Replaced Project',
        jira_project_key: 'REPL',
      };

      mock.onPut(`/projects/${projectId}`).reply(200, { id: projectId, ...replacement });

      await projectsApi.replace(projectId, replacement);

      expect(mock.history.put).toHaveLength(1);
      expect(mock.history.put[0].url).toBe(`/projects/${projectId}`);
    });

    it('test_projects_api_delete_calls_delete', async () => {
      const projectId = '123';

      mock.onDelete(`/projects/${projectId}`).reply(204);

      await projectsApi.delete(projectId);

      expect(mock.history.delete).toHaveLength(1);
      expect(mock.history.delete[0].url).toBe(`/projects/${projectId}`);
    });
  });

  describe('Scores API Methods', () => {
    it('test_scores_api_get_project_scores', async () => {
      const projectId = '123';
      const mockScores = {
        indicators: {},
        scores: {
          p_time: 80,
          p_cost: 90,
          final_score: 85,
        },
      };

      mock.onGet(`/scores/project/${projectId}`).reply(200, mockScores);

      const result = await scoresApi.getProjectScores(projectId);

      expect(result).toEqual(mockScores);
      expect(mock.history.get[0].url).toBe(`/scores/project/${projectId}`);
    });

    it('test_scores_api_calculate_posts_metrics', async () => {
      const metrics: MetricsCreate = {
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        evm_data: {
          budget_total: 100000,
          cost_to_date: 50000,
          percent_completed: 0.5,
          percent_planned: 0.5,
        },
      };

      mock.onPost('/scores/calculate').reply(200, { scores: {} });

      await scoresApi.calculate(metrics, false);

      expect(mock.history.post).toHaveLength(1);
      expect(mock.history.post[0].url).toBe('/scores/calculate');
      const payload = JSON.parse(mock.history.post[0].data);
      expect(payload.metrics).toEqual(metrics);
      expect(payload.sev1_incident).toBe(false);
    });
  });

  describe('Config API Methods', () => {
    it('test_config_api_get', async () => {
      const mockConfig = {
        targets: {},
        global_weights: {},
        constants: {},
      };

      mock.onGet('/config').reply(200, mockConfig);

      const result = await configApi.get();

      expect(result).toEqual(mockConfig);
      expect(mock.history.get[0].url).toBe('/config');
    });

    it('test_config_api_validate', async () => {
      const mockValidation = {
        valid: true,
        groups: { time: true, cost: true },
      };

      mock.onGet('/config/validate').reply(200, mockValidation);

      const result = await configApi.validate();

      expect(result).toEqual(mockValidation);
      expect(mock.history.get[0].url).toBe('/config/validate');
    });
  });

  describe('Collect API Methods', () => {
    it('test_collect_api_jira_metrics', async () => {
      const projectId = '123';
      const mockMetrics: MetricsCreate = {
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        jira_metrics: {
          bugs_closed: 10,
          tasks_completed: 20,
        },
      };

      mock.onPost(`/collect/project/${projectId}/jira`).reply(200, mockMetrics);

      const result = await collectApi.collectJiraMetrics(projectId);

      expect(result).toEqual(mockMetrics);
      expect(mock.history.post[0].url).toBe(`/collect/project/${projectId}/jira`);
    });
  });
});
