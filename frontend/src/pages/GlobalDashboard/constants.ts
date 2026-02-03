import { TIMELINE_CHART_COLORS } from '@/components/ui/timeline-chart';
import type { Dimension } from '../../types';

export const TIMELINE_MONTHS = 36;

// Re-export the shared timeline colors for backwards compatibility
export const TIMELINE_COLORS = TIMELINE_CHART_COLORS;

export const DIMENSION_KEYS = [
  'p_time',
  'p_cost',
  'p_quality',
  'p_value',
  'p_satisfaction',
  'p_flow',
  'p_engineering',
  'p_risk',
] as const;

export type DimensionKey = (typeof DIMENSION_KEYS)[number];

export const DIMENSION_KEY_LABELS: Record<DimensionKey, string> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk Mgmt',
};

export const DIMENSION_KEY_COLORS: Record<DimensionKey, string> = {
  p_time: '#3b82f6',
  p_cost: '#10b981',
  p_quality: '#f59e0b',
  p_value: '#8b5cf6',
  p_satisfaction: '#ec4899',
  p_flow: '#06b6d4',
  p_engineering: '#f97316',
  p_risk: '#ef4444',
};

export const KEY_TO_DIMENSION: Record<DimensionKey, Dimension> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk',
};
