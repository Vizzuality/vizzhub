import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
import api from '../../services/api';
import type { EVMData, Milestone, StrategicImpact } from '../../types';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

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
  jira_defects: { bugs_total: 10, tasks_completed: 100, escaped_defects: 2, incidents_count: 1 },
  flow_metrics: { total_stories: 50, stories_with_reviewer: 45 },
  github_metrics: { prs_without_review: 2, total_merged_prs: 30, high_severity_vulns: 0 },
  test_maturity: { e2e: 80, unit: 90 },
  architecture: { docs_up_to_date: true, iac_implemented: true, adrs_maintained: true, diagrams_updated: true },
  pm_satisfaction: { delivery_complaints: 'no' as const, design_complaints: 'no' as const, overall_estimation: 85 },
  client_survey: { understanding: 90, proactivity: 85 },
  strategic_impact: 'high' as StrategicImpact,
  governance_exceptions: 1,
  sev1_incident: false,
  created_at: '2026-01-15T12:00:00Z',
};

describe('useMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useProjectMetrics', () => {
    it('fetches and returns project metrics', async () => {
      const projectId = 'project-123';
      const mockMetrics = {
        id: 'metrics-1',
        project_id: projectId,
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        tasks_completed: 50,
        tasks_in_progress: 10,
        defects_found: 5,
        defects_escaped: 1,
        created_at: '2026-01-31T12:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue({ data: [mockMetrics] });

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockMetrics);
      expect(api.get).toHaveBeenCalledWith(`/metrics/project/${projectId}`);
    });

    it('returns null when no metrics found (404)', async () => {
      const projectId = 'project-without-metrics';

      vi.mocked(api.get).mockRejectedValue({
        response: { status: 404 },
      });

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
      expect(api.get).not.toHaveBeenCalled();
    });

    it('handles API errors gracefully', async () => {
      const projectId = 'project-123';

      vi.mocked(api.get).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('handles metrics with EVM data', async () => {
      const projectId = 'project-123';
      const mockMetrics = {
        id: 'metrics-1',
        project_id: projectId,
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        tasks_completed: 50,
        evm_data: {
          budget_total: 100000,
          budget_spent: 80000,
          earned_value: 75000,
        },
        created_at: '2026-01-31T12:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue({ data: [mockMetrics] });

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
        id: 'metrics-old',
        project_id: projectId,
        period_start: '2025-12-01',
        period_end: '2025-12-31',
        period_year: 2025,
        period_month: 12,
        created_at: '2026-01-15T12:00:00Z',
      };
      const newerMetrics = {
        id: 'metrics-new',
        project_id: projectId,
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        period_year: 2026,
        period_month: 1,
        created_at: '2026-01-10T12:00:00Z', // Created earlier but more recent period
      };

      vi.mocked(api.get).mockResolvedValue({ data: [olderMetrics, newerMetrics] });

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.id).toBe('metrics-new');
    });

    it('returns null when empty array is returned', async () => {
      const projectId = 'project-123';

      vi.mocked(api.get).mockResolvedValue({ data: [] });

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
      const createdMetrics = {
        id: 'metrics-new',
        project_id: projectId,
        ...metricsToCreate,
        created_at: '2026-01-31T12:00:00Z',
      };

      vi.mocked(api.post).mockResolvedValue({ data: createdMetrics });

      const { result } = renderHook(() => useCreateMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        const response = await result.current.mutateAsync(metricsToCreate);
        expect(response).toEqual(createdMetrics);
      });

      expect(api.post).toHaveBeenCalledWith(`/metrics/project/${projectId}`, metricsToCreate);
    });

    it('handles creation error', async () => {
      const projectId = 'project-123';
      const metricsToCreate = {
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        sev1_incident: false,
      };

      vi.mocked(api.post).mockRejectedValue(new Error('Creation failed'));

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

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, evm_data: evmData },
      });

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(evmData);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          evm_data: evmData,
          milestones: mockExistingMetrics.milestones,
          jira_defects: mockExistingMetrics.jira_defects,
        })
      );
    });

    it('creates EVM data when no existing metrics', async () => {
      const projectId = 'project-123';
      const evmData: EVMData = {
        budget_total: 200000,
        cost_to_date: 100000,
        percent_completed: 60,
        percent_planned: 55,
      };

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', evm_data: evmData },
      });

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(evmData);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          evm_data: evmData,
          sev1_incident: false,
        })
      );
    });
  });

  describe('useUpdateMilestones', () => {
    it('updates milestones with existing metrics', async () => {
      const projectId = 'project-123';
      const milestones: Milestone[] = [
        { name: 'Phase 1', planned_date: '2026-02-01', actual_date: '2026-02-03' },
        { name: 'Phase 2', planned_date: '2026-03-01' },
      ];

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, milestones },
      });

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(milestones);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          milestones,
          evm_data: mockExistingMetrics.evm_data,
        })
      );
    });

    it('creates milestones when no existing metrics', async () => {
      const projectId = 'project-123';
      const milestones: Milestone[] = [
        { name: 'Phase 1', planned_date: '2026-02-01' },
      ];

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', milestones },
      });

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(milestones);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          milestones,
          sev1_incident: false,
        })
      );
    });
  });

  describe('useUpdateGovernance', () => {
    it('updates governance exceptions with existing metrics', async () => {
      const projectId = 'project-123';
      const governanceExceptions = 2;

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, governance_exceptions: governanceExceptions },
      });

      const { result } = renderHook(
        () => useUpdateGovernance(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(governanceExceptions);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          governance_exceptions: governanceExceptions,
          evm_data: mockExistingMetrics.evm_data,
        })
      );
    });

    it('creates governance with zero exceptions', async () => {
      const projectId = 'project-123';

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', governance_exceptions: 0 },
      });

      const { result } = renderHook(
        () => useUpdateGovernance(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(0);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          governance_exceptions: 0,
        })
      );
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

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, pm_satisfaction: pmSatisfaction },
      });

      const { result } = renderHook(
        () => useUpdatePMSatisfaction(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(pmSatisfaction);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          pm_satisfaction: pmSatisfaction,
          evm_data: mockExistingMetrics.evm_data,
        })
      );
    });

    it('handles dash values for complaints', async () => {
      const projectId = 'project-123';
      const pmSatisfaction = {
        delivery_complaints: '-' as const,
        design_complaints: '-' as const,
      };

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', pm_satisfaction: pmSatisfaction },
      });

      const { result } = renderHook(
        () => useUpdatePMSatisfaction(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(pmSatisfaction);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          pm_satisfaction: pmSatisfaction,
        })
      );
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

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, test_maturity: testMaturity },
      });

      const { result } = renderHook(
        () => useUpdateTestMaturity(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(testMaturity);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          test_maturity: testMaturity,
          evm_data: mockExistingMetrics.evm_data,
        })
      );
    });

    it('creates test maturity with partial values', async () => {
      const projectId = 'project-123';
      const testMaturity = {
        unit: 90,
      };

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', test_maturity: testMaturity },
      });

      const { result } = renderHook(
        () => useUpdateTestMaturity(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(testMaturity);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          test_maturity: testMaturity,
        })
      );
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

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, architecture },
      });

      const { result } = renderHook(
        () => useUpdateArchitecture(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(architecture);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          architecture,
          evm_data: mockExistingMetrics.evm_data,
        })
      );
    });

    it('creates architecture with all false values', async () => {
      const projectId = 'project-123';
      const architecture = {
        docs_up_to_date: false,
        iac_implemented: false,
        adrs_maintained: false,
        diagrams_updated: false,
      };

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', architecture },
      });

      const { result } = renderHook(
        () => useUpdateArchitecture(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(architecture);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          architecture,
        })
      );
    });
  });

  describe('useUpdateStrategicImpact', () => {
    it('updates strategic impact with existing metrics', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'transformational';

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, strategic_impact: strategicImpact },
      });

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          strategic_impact: strategicImpact,
          client_survey: mockExistingMetrics.client_survey,
        })
      );
    });

    it('creates strategic impact with low value', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'low';

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', strategic_impact: strategicImpact },
      });

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          strategic_impact: strategicImpact,
        })
      );
    });

    it('handles medium strategic impact', async () => {
      const projectId = 'project-123';
      const strategicImpact: StrategicImpact = 'medium';

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', strategic_impact: strategicImpact },
      });

      const { result } = renderHook(
        () => useUpdateStrategicImpact(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(strategicImpact);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          strategic_impact: strategicImpact,
        })
      );
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

      vi.mocked(api.post).mockResolvedValue({
        data: { ...mockExistingMetrics, client_survey: clientSurvey },
      });

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, mockExistingMetrics),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          client_survey: clientSurvey,
          strategic_impact: mockExistingMetrics.strategic_impact,
        })
      );
    });

    it('creates client survey with partial values', async () => {
      const projectId = 'project-123';
      const clientSurvey = {
        understanding: 80,
        recommend: 85,
      };

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', client_survey: clientSurvey },
      });

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          client_survey: clientSurvey,
        })
      );
    });

    it('handles empty client survey', async () => {
      const projectId = 'project-123';
      const clientSurvey = {};

      vi.mocked(api.post).mockResolvedValue({
        data: { id: 'new-metrics', client_survey: clientSurvey },
      });

      const { result } = renderHook(
        () => useUpdateClientSurvey(projectId, null),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.mutateAsync(clientSurvey);
      });

      expect(api.post).toHaveBeenCalledWith(
        `/metrics/project/${projectId}`,
        expect.objectContaining({
          client_survey: clientSurvey,
        })
      );
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

      vi.mocked(api.post).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(
        () => useUpdateEVMData(projectId, null),
        { wrapper: createWrapper() }
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
      const milestones: Milestone[] = [{ name: 'Phase 1', planned_date: '2026-02-01' }];

      vi.mocked(api.post).mockRejectedValue({
        response: { status: 400, data: { detail: 'Invalid milestone data' } },
      });

      const { result } = renderHook(
        () => useUpdateMilestones(projectId, null),
        { wrapper: createWrapper() }
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
