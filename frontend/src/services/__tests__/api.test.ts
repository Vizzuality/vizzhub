import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/core/services/client';
import { projectsApi } from '@/core/services/projects';
import { scoresApi, configApi } from '@/modules/scorecard/services/scores';
import type { Project, ProjectCreate, MetricsCreate, ScoreResponse, ScoringConfig } from '@/types';

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

  describe('Axios Config', () => {
    it('has withCredentials enabled', () => {
      expect(api.defaults.withCredentials).toBe(true);
    });
  });

  describe('Response Interceptor', () => {
    it('clears user cache and redirects on 401', async () => {
      localStorage.setItem('auth_user', JSON.stringify({ id: '123' }));

      mock.onGet('/projects').reply(401);

      delete (window as unknown as { location?: Location }).location;
      (window as unknown as { location: { href: string } }).location = { href: '' };

      try {
        await projectsApi.list();
      } catch {
        // Expected to throw
      }

      expect(localStorage.getItem('auth_user')).toBeNull();
      expect((window as unknown as { location: { href: string } }).location.href).toBe('/login');
    });

    it('does not intercept 403 errors', async () => {
      localStorage.setItem('auth_user', JSON.stringify({ id: '123' }));

      mock.onGet('/projects').reply(403);

      delete (window as unknown as { location?: Location }).location;
      (window as unknown as { location: { href: string } }).location = { href: '' };

      try {
        await projectsApi.list();
        expect.fail('Should have thrown error');
      } catch {
        expect(localStorage.getItem('auth_user')).toBe(JSON.stringify({ id: '123' }));
        expect((window as unknown as { location: { href: string } }).location.href).toBe('');
      }
    });

    it('does not intercept 500 errors', async () => {
      localStorage.setItem('auth_user', JSON.stringify({ id: '123' }));

      mock.onGet('/projects').reply(500);

      delete (window as unknown as { location?: Location }).location;
      (window as unknown as { location: { href: string } }).location = { href: '' };

      try {
        await projectsApi.list();
        expect.fail('Should have thrown error');
      } catch {
        expect(localStorage.getItem('auth_user')).toBe(JSON.stringify({ id: '123' }));
        expect((window as unknown as { location: { href: string } }).location.href).toBe('');
      }
    });
  });

  describe('Projects API', () => {
    const mockProject: Project = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      name: 'Test Project',
      jira_project_key: 'TEST',
      github_repo: 'org/repo',
      start_date: '2026-01-01',
      end_date: '2026-06-30',
      status: 'live',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };

    describe('list', () => {
      it('fetches paginated projects', async () => {
        const paginatedResponse = {
          items: [mockProject],
          total: 1,
          page: 1,
          page_size: 45,
          pages: 1,
        };
        mock.onGet('/projects').reply(200, paginatedResponse);

        const result = await projectsApi.list();

        expect(result).toEqual(paginatedResponse);
        expect(mock.history.get[0].url).toBe('/projects');
      });

      it('passes query params', async () => {
        const paginatedResponse = {
          items: [],
          total: 0,
          page: 1,
          page_size: 45,
          pages: 1,
        };
        mock.onGet('/projects').reply(200, paginatedResponse);

        await projectsApi.list({ search: 'test', page: 2 });

        expect(mock.history.get[0].params).toEqual({ search: 'test', page: 2 });
      });
    });

    describe('listScorecard', () => {
      it('adds has_scorecard param', async () => {
        const paginatedResponse = {
          items: [],
          total: 0,
          page: 1,
          page_size: 45,
          pages: 1,
        };
        mock.onGet('/projects').reply(200, paginatedResponse);

        await projectsApi.listScorecard({ search: 'test', page: 2 });

        expect(mock.history.get[0].params).toEqual({ search: 'test', page: 2, has_scorecard: true });
      });
    });

    describe('get', () => {
      it('fetches project by id', async () => {
        const projectId = '123e4567-e89b-12d3-a456-426614174000';
        mock.onGet(`/projects/${projectId}`).reply(200, mockProject);

        const result = await projectsApi.get(projectId);

        expect(result.id).toBe(projectId);
        expect(mock.history.get[0].url).toBe(`/projects/${projectId}`);
      });

      it('throws error when project not found', async () => {
        const projectId = 'nonexistent';
        mock.onGet(`/projects/${projectId}`).reply(404, { detail: 'Project not found' });

        await expect(projectsApi.get(projectId)).rejects.toThrow();
      });
    });

    describe('create', () => {
      it('creates new project', async () => {
        const projectData: ProjectCreate = {
          name: 'New Project',
          jira_project_key: 'NEW',
          github_repo: 'org/new-repo',
        };

        mock.onPost('/projects').reply(201, { ...mockProject, ...projectData });

        const result = await projectsApi.create(projectData);

        expect(result.name).toBe('New Project');
        expect(mock.history.post[0].url).toBe('/projects');
        expect(JSON.parse(mock.history.post[0].data)).toEqual(projectData);
      });

      it('creates project with minimal data', async () => {
        const projectData: ProjectCreate = {
          name: 'Minimal Project',
        };

        mock.onPost('/projects').reply(201, {
          ...mockProject,
          ...projectData,
          jira_project_key: null,
          github_repo: null,
        });

        const result = await projectsApi.create(projectData);

        expect(result.name).toBe('Minimal Project');
      });
    });

    describe('update', () => {
      it('updates project with partial data', async () => {
        const projectId = '123e4567-e89b-12d3-a456-426614174000';
        const updateData = { name: 'Updated Name' };

        mock.onPatch(`/projects/${projectId}`).reply(200, { ...mockProject, ...updateData });

        const result = await projectsApi.update(projectId, updateData);

        expect(result.name).toBe('Updated Name');
        expect(mock.history.patch[0].url).toBe(`/projects/${projectId}`);
      });

      it('updates project status', async () => {
        const projectId = '123e4567-e89b-12d3-a456-426614174000';
        const updateData = { status: 'finished' as const };

        mock.onPatch(`/projects/${projectId}`).reply(200, { ...mockProject, ...updateData });

        const result = await projectsApi.update(projectId, updateData);

        expect(result.status).toBe('finished');
      });
    });

    describe('replace', () => {
      it('replaces entire project', async () => {
        const projectId = '123e4567-e89b-12d3-a456-426614174000';
        const projectData: ProjectCreate = {
          name: 'Replaced Project',
          jira_project_key: 'REPLACED',
        };

        mock.onPut(`/projects/${projectId}`).reply(200, { ...mockProject, ...projectData });

        const result = await projectsApi.replace(projectId, projectData);

        expect(result.name).toBe('Replaced Project');
        expect(mock.history.put[0].url).toBe(`/projects/${projectId}`);
      });
    });

    describe('delete', () => {
      it('deletes project', async () => {
        const projectId = '123e4567-e89b-12d3-a456-426614174000';
        mock.onDelete(`/projects/${projectId}`).reply(204);

        await projectsApi.delete(projectId);

        expect(mock.history.delete[0].url).toBe(`/projects/${projectId}`);
      });

      it('throws error when project not found', async () => {
        const projectId = 'nonexistent';
        mock.onDelete(`/projects/${projectId}`).reply(404, { detail: 'Project not found' });

        await expect(projectsApi.delete(projectId)).rejects.toThrow();
      });
    });
  });

  describe('Scores API', () => {
    const mockScoreResponse: ScoreResponse = {
      indicators: {
        spi: 0.95,
        on_time_milestones: 0.8,
        cpi: 1.02,
        cost_variance_pct: 0.05,
        defect_density: 0.02,
        escaped_rate: 0.01,
        mttr_hours: 4,
        governance_compliance: 0.9,
        lead_time_days: 5,
        commitment_reliability: 0.85,
        pr_review_ratio: 0.95,
        prs_without_review: 2,
        high_vulns: 0,
        test_maturity: 0.8,
        arch_checklist: 0.75,
        story_review_ratio: 0.9,
        okr_impact: 0.7,
        pm_satisfaction: 0.85,
        client_satisfaction: 0.9,
        pr_size_median: 150,
        review_turnaround_hours: 8,
        deployment_frequency: 2,
        change_failure_rate: 0.05,
        post_contract_tasks: 5,
      },
      scores: {
        score: 85,
        dimensions: {
          p_time: 90,
          p_cost: 88,
          p_quality: 82,
          p_value: 85,
          p_satisfaction: 88,
          p_flow: 80,
          p_engineering: 85,
          p_risk: 90,
        },
        weights_applied: {
          time: 0.15,
          cost: 0.15,
          quality: 0.15,
          value: 0.1,
          satisfaction: 0.1,
          flow: 0.1,
          engineering: 0.15,
          risk: 0.1,
        },
        dora: null,
      },
    };

    describe('getProjectScores', () => {
      it('fetches scores for project', async () => {
        const projectId = 'project-123';
        mock.onGet(`/scores/project/${projectId}`).reply(200, mockScoreResponse);

        const result = await scoresApi.getProjectScores(projectId);

        expect(result.scores.score).toBe(85);
        expect(mock.history.get[0].url).toBe(`/scores/project/${projectId}`);
      });
    });

    describe('getScoreHistory', () => {
      it('fetches score history with default limit', async () => {
        const projectId = 'project-123';
        mock.onGet(`/scores/project/${projectId}/history`).reply(200, [mockScoreResponse]);

        const result = await scoresApi.getScoreHistory(projectId);

        expect(result).toHaveLength(1);
        expect(mock.history.get[0].params).toEqual({ limit: 10 });
      });

      it('fetches score history with custom limit', async () => {
        const projectId = 'project-123';
        mock.onGet(`/scores/project/${projectId}/history`).reply(200, [mockScoreResponse]);

        await scoresApi.getScoreHistory(projectId, 5);

        expect(mock.history.get[0].params).toEqual({ limit: 5 });
      });
    });

    describe('calculate', () => {
      it('calculates scores from metrics', async () => {
        const metrics: MetricsCreate = {
          period_start: '2026-01-01',
          period_end: '2026-01-31',
          sev1_incident: false,
        };

        mock.onPost('/scores/calculate').reply(200, mockScoreResponse);

        const result = await scoresApi.calculate(metrics);

        expect(result.scores.score).toBe(85);
        expect(mock.history.post[0].url).toBe('/scores/calculate');
      });

      it('calculates scores with sev1 incident', async () => {
        const metrics: MetricsCreate = {
          period_start: '2026-01-01',
          period_end: '2026-01-31',
          sev1_incident: true,
        };

        mock.onPost('/scores/calculate').reply(200, mockScoreResponse);

        await scoresApi.calculate(metrics, true);

        const requestData = JSON.parse(mock.history.post[0].data);
        expect(requestData.sev1_incident).toBe(true);
      });

      it('defaults sev1_incident to false', async () => {
        const metrics: MetricsCreate = {
          period_start: '2026-01-01',
          period_end: '2026-01-31',
          sev1_incident: false,
        };

        mock.onPost('/scores/calculate').reply(200, mockScoreResponse);

        await scoresApi.calculate(metrics);

        const requestData = JSON.parse(mock.history.post[0].data);
        expect(requestData.sev1_incident).toBe(false);
      });
    });
  });

  describe('Config API', () => {
    const mockConfig: ScoringConfig = {
      targets: {
        defect_density: 0.05,
        escaped_rate: 0.02,
        mttr_hours: 4,
        spi: 1.0,
        cpi: 1.0,
        lead_time_days: 7,
        high_vuln_count: 0,
        gov_exceptions: 0,
        pr_no_review_ratio: 0.1,
        pr_size_lines: 200,
        review_turnaround_hours: 24,
        deployment_frequency: 1,
        change_failure_rate: 0.15,
        post_contract_tasks: 0,
      },
      global_weights: {
        time: 0.15,
        cost: 0.15,
        quality: 0.15,
        value: 0.1,
        satisfaction: 0.1,
        flow: 0.1,
        engineering: 0.15,
        risk: 0.1,
      },
      constants: {
        sev1_cap: 60,
        grace_days: 3,
      },
      weight_validation: {
        global: true,
      },
    };

    describe('get', () => {
      it('fetches config', async () => {
        mock.onGet('/config').reply(200, mockConfig);

        const result = await configApi.get();

        expect(result.targets.defect_density).toBe(0.05);
        expect(mock.history.get[0].url).toBe('/config');
      });
    });

    describe('validate', () => {
      it('validates config and returns result', async () => {
        const validationResult = {
          valid: true,
          groups: { global: true, time: true, cost: true },
        };

        mock.onGet('/config/validate').reply(200, validationResult);

        const result = await configApi.validate();

        expect(result.valid).toBe(true);
        expect(result.groups.global).toBe(true);
      });

      it('returns errors when config is invalid', async () => {
        const validationResult = {
          valid: false,
          groups: { global: false },
          errors: ['Global weights must sum to 1.0'],
        };

        mock.onGet('/config/validate').reply(200, validationResult);

        const result = await configApi.validate();

        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Global weights must sum to 1.0');
      });
    });

    describe('updateParameters', () => {
      it('updates config parameters', async () => {
        const updates = [
          { name: 'targets.defect_density', value: '0.03' },
          { name: 'targets.escaped_rate', value: '0.01' },
        ];

        mock.onPatch('/config/parameters').reply(200);

        await configApi.updateParameters(updates);

        expect(mock.history.patch[0].url).toBe('/config/parameters');
        const requestData = JSON.parse(mock.history.patch[0].data);
        expect(requestData.updates).toEqual(updates);
      });
    });
  });

});
