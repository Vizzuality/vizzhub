import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  useProjectMetrics,
  useCreateMetrics,
  useUpdateEVMData,
  useUpdateMilestones,
  useUpdateGovernance,
  useUpdatePMSatisfaction,
  useUpdateTestMaturity,
  useUpdateArchitecture,
  useUpdateStrategicImpact,
  useUpdateClientSurvey,
} from '../useMetrics';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';
import type { EVMData, Milestone, StrategicImpact } from '../../types';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
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

const mockExistingMetrics = {
  id: 'metrics-1',
  project_id: 'project-123',
  period_start: '2026-01-01',
  period_end: '2026-01-15',
  evm_data: {
    budget_total: 100000,
    cost_to_date: 50000,
    percent_completed: 50,
    percent_planned: 50,
  },
  milestones: [{ name: 'Phase 1', planned_date: '2026-02-01' }],
  jira_defects: {
    bugs_total: 10,
    tasks_completed: 100,
    escaped_defects: 2,
    incidents_count: 1,
  },
  flow_metrics: { total_stories: 50, stories_with_reviewer: 45 },
  github_metrics: {
    prs_without_review: 2,
    total_merged_prs: 30,
    high_severity_vulns: 0,
  },
  test_maturity: { e2e: 80, unit: 90 },
  architecture: {
    docs_up_to_date: true,
    iac_implemented: true,
    adrs_maintained: true,
    diagrams_updated: true,
  },
  pm_satisfaction: {
    delivery_complaints: 'no' as const,
    design_complaints: 'no' as const,
    overall_estimation: 85,
  },
  client_survey: { understanding: 90, proactivity: 85 },
  strategic_impact: 'high' as StrategicImpact,
  governance_exceptions: 1,
  sev1_incident: false,
  created_at: '2026-01-15T12:00:00Z',
};

describe('useMetrics', () => {
  describe('useProjectMetrics', () => {
    it('fetches and returns project metrics', async () => {
      const projectId = 'project-123';

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(fixtures.metrics);
    });

    it('returns null when no metrics found (404)', async () => {
      const projectId = 'project-without-metrics';

      server.use(
        http.get('/api/metrics/project/:projectId', () => {
          return HttpResponse.json(
            { detail: 'Not found' },
            { status: 404 },
          );
        }),
      );

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useProjectMetrics(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
    });

    it('handles API errors gracefully', async () => {
      const projectId = 'project-123';

      server.use(
        http.get('/api/metrics/project/:projectId', () => {
          return HttpResponse.error();
        }),
      );

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('handles metrics with EVM data', async () => {
      const projectId = 'project-123';
      const metricsWithEvm = {
        ...fixtures.metrics,
        evm_data: {
          budget_total: 100000,
          budget_spent: 80000,
          earned_value: 75000,
        },
      };

      server.use(
        http.get('/api/metrics/project/:projectId', () => {
          return HttpResponse.json([metricsWithEvm]);
        }),
      );

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.evm_data).toBeDefined();
      expect(result.current.data?.evm_data?.budget_total).toBe(100000);
    });

    it('returns the most recent metrics when multiple exist', async () => {
      const projectId = 'project-123';
      const olderMetrics = {
        ...fixtures.metrics,
        id: 'metrics-old',
        period_start: '2025-12-01',
        period_end: '2025-12-31',
        period_year: 2025,
        period_month: 12,
        created_at: '2026-01-15T12:00:00Z',
      };
      const newerMetrics = {
        ...fixtures.metrics,
        id: 'metrics-new',
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        period_year: 2026,
        period_month: 1,
        created_at: '2026-01-10T12:00:00Z',
      };

      server.use(
        http.get('/api/metrics/project/:projectId', () => {
          return HttpResponse.json([olderMetrics, newerMetrics]);
        }),
      );

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.id).toBe('metrics-new');
    });

    it('returns null when empty array is returned', async () => {
      const projectId = 'project-123';

      server.use(
        http.get('/api/metrics/project/:projectId', () => {
          return HttpResponse.json([]);
        }),
      );

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });
  });

  describe('useCreateMetrics', () => {
    it('creates new metrics successfully', async () => {
      const projectId = 'project-123';
      const metricsToCreate = {
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        sev1_incident: false,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({
            id: 'metrics-new',
            project_id: projectId,
            ...capturedBody,
            created_at: '2026-01-31T12:00:00Z',
          });
        }),
      );

      const { result } = renderHook(() => useCreateMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        const response = await result.current.mutateAsync(metricsToCreate);
        expect(response.id).toBe('metrics-new');
        expect(response.project_id).toBe(projectId);
      });

      expect(capturedBody).toMatchObject(metricsToCreate);
    });

    it('handles creation error', async () => {
      const projectId = 'project-123';
      const metricsToCreate = {
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        sev1_incident: false,
      };

      server.use(
        http.post('/api/metrics/project/:projectId', () => {
          return HttpResponse.json(
            { detail: 'Creation failed' },
            { status: 500 },
          );
        }),
      );

      const { result } = renderHook(() => useCreateMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        try {
          await result.current.mutateAsync(metricsToCreate);
        } catch (error) {
          expect(error).toBeDefined();
        }
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useUpdateEVMData', () => {
    it('updates EVM data with existing metrics', async () => {
      const projectId = 'project-123';
      const evmData: EVMData = {
        budget_total: 200000,
        cost_to_date: 100000,
        percent_completed: 60,
        percent_planned: 55,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(evmData);
      });

      expect(capturedBody).toMatchObject({
        evm_data: evmData,
        milestones: mockExistingMetrics.milestones,
        jira_defects: mockExistingMetrics.jira_defects,
      });
    });

    it('creates EVM data when no existing metrics', async () => {
      const projectId = 'project-123';
      const evmData: EVMData = {
        budget_total: 200000,
        cost_to_date: 100000,
        percent_completed: 60,
        percent_planned: 55,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(evmData);
      });

      expect(capturedBody).toMatchObject({
        evm_data: evmData,
        sev1_incident: false,
      });
    });
  });

  describe('useUpdateMilestones', () => {
    it('updates milestones with existing metrics', async () => {
      const projectId = 'project-123';
      const milestones: Milestone[] = [
        { name: 'Phase 1', planned_date: '2026-02-01', actual_date: '2026-02-03' },
        { name: 'Phase 2', planned_date: '2026-03-01' },
      ];

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(milestones);
      });

      expect(capturedBody).toMatchObject({
        milestones,
        evm_data: mockExistingMetrics.evm_data,
      });
    });

    it('creates milestones when no existing metrics', async () => {
      const projectId = 'project-123';
      const milestones: Milestone[] = [
        { name: 'Phase 1', planned_date: '2026-02-01' },
      ];

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(milestones);
      });

      expect(capturedBody).toMatchObject({
        milestones,
        sev1_incident: false,
      });
    });
  });

  describe('useUpdateGovernance', () => {
    it('updates governance exceptions with existing metrics', async () => {
      const projectId = 'project-123';
      const governanceExceptions = 2;

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateGovernance(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(governanceExceptions);
      });

      expect(capturedBody).toMatchObject({
        governance_exceptions: governanceExceptions,
        evm_data: mockExistingMetrics.evm_data,
      });
    });

    it('creates governance with zero exceptions', async () => {
      const projectId = 'project-123';

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateGovernance(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(0);
      });

      expect(capturedBody).toMatchObject({
        governance_exceptions: 0,
      });
    });
  });

  describe('useUpdatePMSatisfaction', () => {
    it('updates PM satisfaction with existing metrics', async () => {
      const projectId = 'project-123';
      const pmSatisfaction = {
        delivery_complaints: 'no' as const,
        design_complaints: 'yes' as const,
        overall_estimation: 75,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdatePMSatisfaction(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(pmSatisfaction);
      });

      expect(capturedBody).toMatchObject({
        pm_satisfaction: pmSatisfaction,
        evm_data: mockExistingMetrics.evm_data,
      });
    });

    it('handles dash values for complaints', async () => {
      const projectId = 'project-123';
      const pmSatisfaction = {
        delivery_complaints: '-' as const,
        design_complaints: '-' as const,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdatePMSatisfaction(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(pmSatisfaction);
      });

      expect(capturedBody).toMatchObject({
        pm_satisfaction: pmSatisfaction,
      });
    });
  });

  describe('useUpdateTestMaturity', () => {
    it('updates test maturity with existing metrics', async () => {
      const projectId = 'project-123';
      const testMaturity = {
        e2e: 85,
        unit: 95,
        accessibility: 70,
        security: 60,
        frontend: 80,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateTestMaturity(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(testMaturity);
      });

      expect(capturedBody).toMatchObject({
        test_maturity: testMaturity,
        evm_data: mockExistingMetrics.evm_data,
      });
    });

    it('creates test maturity with partial values', async () => {
      const projectId = 'project-123';
      const testMaturity = {
        unit: 90,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateTestMaturity(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(testMaturity);
      });

      expect(capturedBody).toMatchObject({
        test_maturity: testMaturity,
      });
    });
  });

  describe('useUpdateArchitecture', () => {
    it('updates architecture with existing metrics', async () => {
      const projectId = 'project-123';
      const architecture = {
        docs_up_to_date: true,
        iac_implemented: false,
        adrs_maintained: true,
        diagrams_updated: false,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateArchitecture(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(architecture);
      });

      expect(capturedBody).toMatchObject({
        architecture,
        evm_data: mockExistingMetrics.evm_data,
      });
    });

    it('creates architecture with all false values', async () => {
      const projectId = 'project-123';
      const architecture = {
        docs_up_to_date: false,
        iac_implemented: false,
        adrs_maintained: false,
        diagrams_updated: false,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateArchitecture(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(architecture);
      });

      expect(capturedBody).toMatchObject({
        architecture,
      });
    });
  });

  describe('useUpdateStrategicImpact', () => {
    it('updates strategic impact with existing metrics', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'transformational';

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(capturedBody).toMatchObject({
        strategic_impact: strategicImpact,
        client_survey: mockExistingMetrics.client_survey,
      });
    });

    it('creates strategic impact with low value', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'low';

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(capturedBody).toMatchObject({
        strategic_impact: strategicImpact,
      });
    });

    it('handles medium strategic impact', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'medium';

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(capturedBody).toMatchObject({
        strategic_impact: strategicImpact,
      });
    });
  });

  describe('useUpdateClientSurvey', () => {
    it('updates client survey with existing metrics', async () => {
      const projectId = 'project-123';
      const clientSurvey = {
        understanding: 95,
        proactivity: 90,
        communication: 85,
        delivery_time: 80,
        response_time: 75,
        quality: 90,
        expectations: 85,
        recommend: 95,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, mockExistingMetrics),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(capturedBody).toMatchObject({
        client_survey: clientSurvey,
        strategic_impact: mockExistingMetrics.strategic_impact,
      });
    });

    it('creates client survey with partial values', async () => {
      const projectId = 'project-123';
      const clientSurvey = {
        understanding: 80,
        recommend: 85,
      };

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(capturedBody).toMatchObject({
        client_survey: clientSurvey,
      });
    });

    it('handles empty client survey', async () => {
      const projectId = 'project-123';
      const clientSurvey = {};

      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post('/api/metrics/project/:projectId', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({ ...fixtures.metrics, ...capturedBody });
        }),
      );

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(capturedBody).toMatchObject({
        client_survey: clientSurvey,
      });
    });
  });

  describe('mutation error handling', () => {
    it('handles network errors in EVM update', async () => {
      const projectId = 'project-123';
      const evmData: EVMData = {
        budget_total: 200000,
        cost_to_date: 100000,
        percent_completed: 60,
        percent_planned: 55,
      };

      server.use(
        http.post('/api/metrics/project/:projectId', () => {
          return HttpResponse.error();
        }),
      );

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        try {
          await result.current.mutateAsync(evmData);
        } catch (error) {
          expect(error).toBeDefined();
        }
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });

    it('handles API errors in milestone update', async () => {
      const projectId = 'project-123';
      const milestones: Milestone[] = [
        { name: 'Phase 1', planned_date: '2026-02-01' },
      ];

      server.use(
        http.post('/api/metrics/project/:projectId', () => {
          return HttpResponse.json(
            { detail: 'Invalid milestone data' },
            { status: 400 },
          );
        }),
      );

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, null),
        { wrapper: createWrapper() },
      );

      await act(async () => {
        try {
          await result.current.mutateAsync(milestones);
        } catch (error) {
          expect(error).toBeDefined();
        }
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });
});
