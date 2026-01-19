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
  });

  describe('Projects API Methods', () => {
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
  });

});
