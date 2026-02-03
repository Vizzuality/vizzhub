import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useGlobalMetrics,
  useGlobalMetricsHistory,
  useAvailableGlobalMonths,
  useCalculateGlobalMetrics,
  useRecalculateGlobalMetrics,
} from '../useGlobalMetrics';
import { globalMetricsApi } from '../../services/api';
import type {
  GlobalMetricsRecord,
  AvailableMonth,
  CalculateBatchResponse,
} from '../../types/global';

vi.mock('../../services/api', () => ({
  globalMetricsApi: {
    getRecord: vi.fn(),
    getHistory: vi.fn(),
    getAvailableMonths: vi.fn(),
    calculate: vi.fn(),
    recalculate: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const mockGlobalMetricsRecord: GlobalMetricsRecord = {
  id: 'record-123',
  period_year: 2024,
  period_month: 12,
  project_count: 5,
  indicators: {
    spi: { value: 0.95, count: 5 },
    cpi: { value: 0.88, count: 4 },
    on_time_milestones: { value: 0.8, count: 3 },
    defect_density: { value: 2.5, count: 5 },
    escaped_rate: { value: 0.02, count: 5 },
    mttr_hours: { value: 24, count: 4 },
    governance_compliance: { value: 0.9, count: 5 },
    lead_time_days: { value: 4.2, count: 5 },
    deployment_frequency: { value: 1.5, count: 3 },
    change_failure_rate: { value: 0.08, count: 3 },
    commitment_reliability: { value: 0.85, count: 5 },
    pr_review_ratio: { value: 0.92, count: 5 },
    test_maturity: { value: 0.78, count: 4 },
    arch_checklist: { value: 0.65, count: 3 },
    high_vulns: { value: 0, count: 5 },
    okr_impact: { value: null, count: 0 },
    pm_satisfaction: { value: 0.8, count: 4 },
    client_satisfaction: { value: null, count: 0 },
    story_review_ratio: { value: 0.88, count: 5 },
    strategic_impact: { value: null, count: 0 },
  },
  scores: {
    score: { value: 78.5, count: 5 },
    p_time: { value: 82, count: 5 },
    p_cost: { value: 75, count: 4 },
    p_quality: { value: 80, count: 5 },
    p_value: { value: 70, count: 3 },
    p_satisfaction: { value: 78, count: 4 },
    p_flow: { value: 76, count: 5 },
    p_engineering: { value: 72, count: 4 },
    p_risk: { value: 85, count: 5 },
  },
  created_at: '2024-12-31T23:59:59Z',
  updated_at: '2024-12-31T23:59:59Z',
};

describe('useGlobalMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useGlobalMetrics', () => {
    it('fetches and returns global metrics for a specific month', async () => {
      vi.mocked(globalMetricsApi.getRecord).mockResolvedValue(mockGlobalMetricsRecord);

      const { result } = renderHook(() => useGlobalMetrics(2024, 12), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockGlobalMetricsRecord);
      expect(globalMetricsApi.getRecord).toHaveBeenCalledWith(2024, 12);
    });

    it('returns null when no metrics exist for the month', async () => {
      vi.mocked(globalMetricsApi.getRecord).mockResolvedValue(null);

      const { result } = renderHook(() => useGlobalMetrics(2020, 1), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('handles API errors', async () => {
      vi.mocked(globalMetricsApi.getRecord).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useGlobalMetrics(2024, 12), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useGlobalMetricsHistory', () => {
    it('fetches history with default limit', async () => {
      const mockHistory = [
        mockGlobalMetricsRecord,
        { ...mockGlobalMetricsRecord, id: 'record-456', period_month: 11 },
      ];
      vi.mocked(globalMetricsApi.getHistory).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useGlobalMetricsHistory(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockHistory);
      expect(globalMetricsApi.getHistory).toHaveBeenCalledWith(12);
    });

    it('fetches history with custom limit', async () => {
      const mockHistory = [mockGlobalMetricsRecord];
      vi.mocked(globalMetricsApi.getHistory).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useGlobalMetricsHistory(6), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(globalMetricsApi.getHistory).toHaveBeenCalledWith(6);
    });

    it('returns empty array when no history exists', async () => {
      vi.mocked(globalMetricsApi.getHistory).mockResolvedValue([]);

      const { result } = renderHook(() => useGlobalMetricsHistory(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([]);
    });
  });

  describe('useAvailableGlobalMonths', () => {
    it('fetches available months', async () => {
      const mockMonths: AvailableMonth[] = [
        { year: 2024, month: 12 },
        { year: 2024, month: 11 },
        { year: 2024, month: 10 },
      ];
      vi.mocked(globalMetricsApi.getAvailableMonths).mockResolvedValue(mockMonths);

      const { result } = renderHook(() => useAvailableGlobalMonths(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockMonths);
      expect(globalMetricsApi.getAvailableMonths).toHaveBeenCalled();
    });

    it('returns empty array when no months available', async () => {
      vi.mocked(globalMetricsApi.getAvailableMonths).mockResolvedValue([]);

      const { result } = renderHook(() => useAvailableGlobalMonths(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([]);
    });
  });

  describe('useCalculateGlobalMetrics', () => {
    it('calculates global metrics for date range', async () => {
      const mockResponse: CalculateBatchResponse = {
        months_processed: 3,
        records: [mockGlobalMetricsRecord],
      };
      vi.mocked(globalMetricsApi.calculate).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useCalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 10,
          to_year: 2024,
          to_month: 12,
        });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(globalMetricsApi.calculate).toHaveBeenCalledWith({
        from_year: 2024,
        from_month: 10,
        to_year: 2024,
        to_month: 12,
      });
    });

    it('handles calculation errors', async () => {
      vi.mocked(globalMetricsApi.calculate).mockRejectedValue(
        new Error('Invalid date range'),
      );

      const { result } = renderHook(() => useCalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 12,
          to_year: 2024,
          to_month: 10,
        });
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useRecalculateGlobalMetrics', () => {
    it('recalculates global metrics for date range', async () => {
      const mockResponse: CalculateBatchResponse = {
        months_processed: 1,
        records: [mockGlobalMetricsRecord],
      };
      vi.mocked(globalMetricsApi.recalculate).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useRecalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 12,
          to_year: 2024,
          to_month: 12,
        });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(globalMetricsApi.recalculate).toHaveBeenCalledWith({
        from_year: 2024,
        from_month: 12,
        to_year: 2024,
        to_month: 12,
      });
    });
  });
});

describe('GlobalMetricsRecord structure', () => {
  it('has correct indicator fields', () => {
    const indicators = mockGlobalMetricsRecord.indicators;

    expect(indicators).toHaveProperty('spi');
    expect(indicators).toHaveProperty('cpi');
    expect(indicators).toHaveProperty('lead_time_days');
    expect(indicators).toHaveProperty('defect_density');
    expect(indicators).toHaveProperty('pr_review_ratio');
    expect(indicators).toHaveProperty('strategic_impact');

    // Each indicator should have value and count
    expect(indicators.spi).toHaveProperty('value');
    expect(indicators.spi).toHaveProperty('count');
  });

  it('has correct score fields', () => {
    const scores = mockGlobalMetricsRecord.scores;

    expect(scores).toHaveProperty('score');
    expect(scores).toHaveProperty('p_time');
    expect(scores).toHaveProperty('p_cost');
    expect(scores).toHaveProperty('p_quality');
    expect(scores).toHaveProperty('p_value');
    expect(scores).toHaveProperty('p_satisfaction');
    expect(scores).toHaveProperty('p_flow');
    expect(scores).toHaveProperty('p_engineering');
    expect(scores).toHaveProperty('p_risk');

    // Each score should have value and count
    expect(scores.score).toHaveProperty('value');
    expect(scores.score).toHaveProperty('count');
  });

  it('handles null values correctly', () => {
    const indicators = mockGlobalMetricsRecord.indicators;

    // okr_impact has null value and count 0
    expect(indicators.okr_impact.value).toBeNull();
    expect(indicators.okr_impact.count).toBe(0);
  });
});
