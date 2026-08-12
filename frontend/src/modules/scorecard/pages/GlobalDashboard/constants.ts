export const TIMELINE_MONTHS = 36;

// Re-export the shared timeline colors for backwards compatibility
export { TIMELINE_CHART_COLORS as TIMELINE_COLORS } from '@/shared/components/ui/timeline-chart';

// Re-export dimension constants from shared component
export {
  DIMENSION_KEYS,
  DIMENSION_LABELS as DIMENSION_KEY_LABELS,
  DIMENSION_COLORS as DIMENSION_KEY_COLORS,
  KEY_TO_DIMENSION,
  type DimensionKey,
} from '../../components/DimensionChart/DimensionBreakdownCard';
